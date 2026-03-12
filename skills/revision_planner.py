"""Generate a revision plan and markdown report from the logic map."""

from __future__ import annotations

import json


REVISION_ENRICHMENT_SYSTEM_PROMPT = """
You are helping generate revision advice for an academic paper diagnosis report.
Return strict JSON with keys:
- why_it_matters
- how_to_fix
- example_rewrite

Requirements:
- Keep each field concise and actionable.
- Align with Nature-family quality expectations.
- Do not invent experiments or results not present in the source span.
- example_rewrite should be a short improved version of the source idea, not a full paragraph.
""".strip()


def _nature_quality_reason(issue_type: str, journal_profile: dict, nature_quality_rubric: dict) -> str:
    dimensions = nature_quality_rubric["dimensions"]
    mapping = {
        "gap": dimensions["gap_clarity"],
        "contribution": dimensions["contribution_sharpness"],
        "evidence": dimensions["claim_evidence_alignment"],
        "scope": dimensions["claim_scope_control"],
        "validation": dimensions["validation_rigor"],
        "narrative": dimensions["narrative_coherence"],
        "significance": dimensions["significance_framing"],
        "structure": dimensions["narrative_coherence"],
        "readability": dimensions["narrative_coherence"],
        "journal_fit": journal_profile["expects"][0],
    }
    return mapping.get(issue_type, journal_profile["expects"][0])


def _build_fix(
    issue_type: str,
    role: str,
    vulnerability: str,
    evidence_items: list[dict],
    claim_scope_risk: str,
    narrative_link_issue: str,
    significance_risk: str,
) -> str:
    if issue_type == "gap":
        return "Rewrite the opening of the paragraph so it states the unresolved problem in one sentence, then explain why existing work still leaves it open."
    if issue_type == "contribution":
        return "State the core contribution in one sentence using a concrete verb and explicit differentiation from prior work."
    if "lacks explicit evidence" in vulnerability:
        return "Add a direct pointer to the experiment, figure, table, or citation that supports the contribution claim."
    if "does not reference figures" in vulnerability:
        return "Name the exact metric, experiment, figure, or table that justifies the interpretation."
    if issue_type == "scope" or claim_scope_risk == "overclaim":
        return "Narrow the claim so it matches the evidence shown, or add the missing validation that would justify the broader statement."
    if issue_type == "narrative" or narrative_link_issue != "clear":
        return "Insert a bridging sentence that explicitly connects the previous paragraph's point to the role this paragraph now plays."
    if issue_type == "validation":
        return "Add the strongest benchmark, control, ablation, or comparison that proves the method claim at review level."
    if issue_type == "significance":
        if significance_risk == "significance_not_grounded":
            return "Tie the discussion claim to the strongest reported result, then state the broader capability or field consequence that follows from that evidence."
        return "Add one or two sentences that translate the result into broader methodological, user-facing, or field-level significance."
    if role == "Discussion":
        return "Tie the discussion back to the strongest preceding evidence and state the implication explicitly."
    if evidence_items:
        return "Tighten the paragraph so the claim and supporting evidence appear in the same local context."
    return "Rewrite the paragraph around one clear claim followed by one concrete supporting detail."


def _default_why_it_matters(role: str) -> str:
    return f"The paragraph is labeled as {role}, so unclear logic here weakens the paper's narrative flow."


def _enrich_revision_item(
    entry: dict,
    journal_profile: dict,
    nature_quality_rubric: dict,
    llm_client,
) -> dict | None:
    if not llm_client or not llm_client.is_configured:
        return None

    user_prompt = json.dumps(
        {
            "target_quality": journal_profile["journal"],
            "issue_type": entry["issue_type"],
            "role": entry["role"],
            "problem": entry["logical_vulnerability"],
            "source_span": entry["source_text"],
            "claim_text": entry["claim"]["claim_text"],
            "claim_status": entry["claim"]["status"],
            "evidence_items": entry["evidence"]["items"],
            "claim_scope_risk": entry["claim_scope_risk"],
            "narrative_link_issue": entry["narrative_link_issue"],
            "significance_risk": entry["significance_risk"],
            "nature_quality_reason": _nature_quality_reason(
                entry["issue_type"],
                journal_profile,
                nature_quality_rubric,
            ),
        },
        ensure_ascii=False,
        indent=2,
    )
    try:
        enriched = llm_client.chat_json(
            REVISION_ENRICHMENT_SYSTEM_PROMPT,
            user_prompt,
        )
    except Exception:
        return None

    required_keys = {"why_it_matters", "how_to_fix", "example_rewrite"}
    if not isinstance(enriched, dict) or not required_keys.issubset(enriched):
        return None
    return enriched


def build_revision_plan(
    logic_map: dict,
    journal_profile: dict,
    nature_quality_rubric: dict,
    storyline: dict,
    llm_client=None,
) -> dict:
    items: list[dict] = []

    for entry in logic_map["items"]:
        if entry["priority"] >= 4:
            continue
        evidence_values = [item["value"] for item in entry["evidence"]["items"]]
        fallback_fix = _build_fix(
            entry["issue_type"],
            entry["role"],
            entry["logical_vulnerability"],
            entry["evidence"]["items"],
            entry["claim_scope_risk"],
            entry["narrative_link_issue"],
            entry["significance_risk"],
        )
        enriched = _enrich_revision_item(
            entry,
            journal_profile,
            nature_quality_rubric,
            llm_client,
        )
        items.append(
            {
                "paragraph_id": entry["paragraph_id"],
                "problem": entry["logical_vulnerability"],
                "why_it_matters": (
                    enriched["why_it_matters"]
                    if enriched
                    else _default_why_it_matters(entry["role"])
                ),
                "source_span": entry["source_text"],
                "how_to_fix": enriched["how_to_fix"] if enriched else fallback_fix,
                "example_rewrite": (
                    enriched["example_rewrite"]
                    if enriched
                    else (
                        f"{entry['claim']['claim_text'] or 'State the core claim explicitly.'} "
                        "This statement should be followed by a concrete evidence anchor or transition sentence."
                    ).strip()
                ),
                "priority": entry["priority"],
                "issue_type": entry["issue_type"],
                "journal_rationale": _nature_quality_reason(
                    entry["issue_type"],
                    journal_profile,
                    nature_quality_rubric,
                ),
                "claim_status": entry["claim"]["status"],
                "evidence_summary": evidence_values,
                "section": entry["section"],
                "claim_scope_risk": entry["claim_scope_risk"],
                "narrative_link_issue": entry["narrative_link_issue"],
                "significance_risk": entry["significance_risk"],
            }
        )

    items.sort(key=lambda item: (item["priority"], item["paragraph_id"]))
    return {
        "document_name": logic_map["document_name"],
        "journal": journal_profile["journal"],
        "rubric_name": nature_quality_rubric["rubric_name"],
        "item_count": len(items),
        "storyline": storyline,
        "items": items,
    }


def _build_section_groups(items: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(item["section"], []).append(item)
    return grouped


def _build_issue_groups(items: list[dict]) -> dict:
    grouped: dict[str, int] = {}
    for item in items:
        grouped[item["issue_type"]] = grouped.get(item["issue_type"], 0) + 1
    return grouped


def render_revision_report(revision_plan: dict, journal_profile: dict) -> str:
    issue_groups = _build_issue_groups(revision_plan["items"])
    section_groups = _build_section_groups(revision_plan["items"])
    lines = [
        f"# Revision Report: {revision_plan['document_name']}",
        "",
        "## Executive Summary",
        "",
        f"Target journal: {journal_profile['journal']}",
        "",
        f"Total action items: {revision_plan['item_count']}",
        "",
        (
            "Primary risk pattern: "
            + (", ".join(f"{key} ({value})" for key, value in sorted(issue_groups.items())) if issue_groups else "No major risks detected.")
        ),
        "",
        "## Journal Fit Assessment",
        "",
        f"This draft is being assessed against {journal_profile['journal']} quality expectations.",
        "",
        f"Nature-family expectation: {journal_profile['expects'][0]}",
        "",
        f"Key reviewer concern to pre-empt: {journal_profile['common_failures'][0]}",
        "",
        "## Storyline Snapshot",
        "",
        f"Main problem: {revision_plan['storyline']['main_problem']}",
        "",
        f"Main gap: {revision_plan['storyline']['main_gap']}",
        "",
        f"Core contribution: {revision_plan['storyline']['core_contribution']}",
        "",
        "Supporting results: "
        + (", ".join(revision_plan["storyline"]["supporting_results"]) if revision_plan["storyline"]["supporting_results"] else "Not clearly extracted."),
        "",
        "## Top Priority Revisions",
        "",
    ]

    if not revision_plan["items"]:
        lines.extend(["No actionable logic issues detected.", "", "## Questions for Author", "", "- What exact journal-facing claim should be strongest in the current draft?", ""])
        return "\n".join(lines)

    for index, item in enumerate(revision_plan["items"], start=1):
        lines.extend(
            [
                f"## Item {index}: {item['paragraph_id']} (Priority {item['priority']})",
                "",
                f"**Problem**: {item['problem']}",
                "",
                f"**Why it matters**: {item['why_it_matters']}",
                "",
                f"**Issue type**: {item['issue_type']}",
                "",
                f"**Why it matters for Nature-family quality**: {item['journal_rationale']}",
                "",
                f"**Source span**: {item['source_span']}",
                "",
                f"**How to fix**: {item['how_to_fix']}",
                "",
                f"**Claim status**: {item['claim_status']}",
                "",
                f"**Claim scope risk**: {item['claim_scope_risk']}",
                "",
                f"**Narrative link issue**: {item['narrative_link_issue']}",
                "",
                f"**Significance risk**: {item['significance_risk']}",
                "",
                f"**Evidence summary**: {', '.join(item['evidence_summary']) if item['evidence_summary'] else 'None'}",
                "",
                f"**Example rewrite**: {item['example_rewrite']}",
                "",
            ]
        )

    lines.extend(["## Section-by-Section Revision Plan", ""])
    for section, items in section_groups.items():
        lines.append(f"### {section}")
        lines.append("")
        for item in items:
            lines.append(
                f"- {item['paragraph_id']}: {item['problem']} [{item['issue_type']}; priority {item['priority']}]"
            )
        lines.append("")

    lines.extend(["## Evidence / Claim Risk Notes", ""])
    for item in revision_plan["items"]:
        lines.extend(
            [
                f"- {item['paragraph_id']}: claim status is `{item['claim_status']}`; evidence summary is "
                f"{', '.join(item['evidence_summary']) if item['evidence_summary'] else 'None'}; "
                f"scope risk is `{item['claim_scope_risk']}`; narrative link is `{item['narrative_link_issue']}`; "
                f"significance risk is `{item['significance_risk']}`.",
            ]
        )
    lines.extend(["", "## Questions for Author", ""])

    if any(item["issue_type"] == "contribution" for item in revision_plan["items"]):
        lines.append("- What is the single sentence that best distinguishes this method from the strongest existing alternative?")
    if any(item["issue_type"] in {"evidence", "validation"} for item in revision_plan["items"]):
        lines.append("- Which figure, benchmark, control, or comparison most directly proves the main method claim?")
    if any(item["issue_type"] == "scope" for item in revision_plan["items"]):
        lines.append("- Which current claim is broader than the evidence you can actually defend in peer review?")
    if any(item["issue_type"] == "significance" for item in revision_plan["items"]):
        lines.append("- What is the one discussion sentence that makes the broader methodological or field-level significance explicit?")
    else:
        lines.append("- What is the one broad-significance sentence that should make a Nature-family reviewer care about this manuscript?")
    lines.append("")

    return "\n".join(lines)
