"""Build a logic map from role, claim, and evidence annotations."""

from __future__ import annotations

def _detect_issue_type(
    role: str,
    has_claim: bool,
    has_evidence: bool,
    claim_scope_risk: str,
    narrative_link_issue: str,
    significance_risk: str,
) -> str:
    if claim_scope_risk == "overclaim":
        return "scope"
    if claim_scope_risk == "underspecified" and role in {"Contribution", "Background", "Field Context"}:
        return "contribution"
    if role == "Contribution" and not has_claim:
        return "contribution"
    if role == "Contribution" and not has_evidence:
        return "evidence"
    if role == "Result Interpretation" and not has_evidence:
        return "validation"
    if role == "Gap Identification" and not has_claim:
        return "gap"
    if narrative_link_issue != "clear":
        return "narrative"
    if significance_risk != "clear":
        return "significance"
    return "structure"


def _detect_claim_scope_risk(role: str, claim_text: str | None, has_evidence: bool) -> str:
    if not claim_text:
        return "underspecified"
    lower_claim = claim_text.lower()
    if any(marker in lower_claim for marker in ("all", "always", "universally", "solves", "proves")) and not has_evidence:
        return "overclaim"
    if role in {"Contribution", "Result Interpretation"} and not has_evidence:
        return "underspecified"
    return "supported"


def _detect_narrative_link_issue(previous_role: str | None, role: str, has_claim: bool) -> str:
    if role == "Contribution" and previous_role not in {"Gap Identification", "Field Context"}:
        return "missing_gap_to_contribution_bridge"
    if role == "Result Interpretation" and previous_role not in {"Contribution", "Background"}:
        return "weak_result_bridge"
    if role == "Discussion" and not has_claim:
        return "weak_implication_bridge"
    return "clear"


def _detect_significance_risk(role: str, text: str, has_claim: bool, has_evidence: bool) -> str:
    if role != "Discussion":
        return "not_applicable"
    lower_text = text.lower()
    significance_markers = (
        "impact",
        "implication",
        "broader",
        "enable",
        "utility",
        "field",
        "community",
        "application",
    )
    if not has_claim:
        return "missing_significance_claim"
    if not any(marker in lower_text for marker in significance_markers):
        return "weak_significance_framing"
    if not has_evidence:
        return "significance_not_grounded"
    return "clear"


def _dimension_flags(
    role: str,
    has_claim: bool,
    has_evidence: bool,
    claim_scope_risk: str,
    narrative_link_issue: str,
    significance_risk: str,
) -> dict:
    return {
        "gap_clarity": role == "Gap Identification" and has_claim,
        "contribution_sharpness": role == "Contribution" and has_claim,
        "claim_evidence_alignment": not has_claim or has_evidence,
        "claim_scope_control": claim_scope_risk == "supported",
        "validation_rigor": role != "Result Interpretation" or has_evidence,
        "narrative_coherence": narrative_link_issue == "clear",
        "significance_framing": significance_risk in {"clear", "not_applicable"},
    }


def _detect_vulnerability(
    role: str,
    has_claim: bool,
    claim_text: str | None,
    has_evidence: bool,
    claim_scope_risk: str,
    narrative_link_issue: str,
    significance_risk: str,
) -> tuple[str, int]:
    if claim_scope_risk == "overclaim":
        return ("Claim scope appears broader than the support shown in the local paragraph.", 1)
    if role == "Contribution" and not has_claim:
        return ("Contribution paragraph does not state a clear claim.", 1)
    if role == "Contribution" and not has_evidence:
        return ("Contribution claim lacks explicit evidence anchor.", 1)
    if role == "Result Interpretation" and not has_evidence:
        return ("Results paragraph does not reference figures, tables, citations, or concrete result statements.", 1)
    if role == "Gap Identification" and not has_claim:
        return ("Gap paragraph does not clearly state the missing capability or unresolved problem.", 2)
    if narrative_link_issue != "clear":
        return ("Narrative progression into this paragraph is weak and needs a clearer bridge from the previous step.", 2)
    if significance_risk == "missing_significance_claim":
        return ("Discussion does not state the broader significance of the work clearly enough.", 2)
    if significance_risk in {"weak_significance_framing", "significance_not_grounded"}:
        return ("Discussion states limited implication and does not yet frame why the result matters at high-impact level.", 2)
    if claim_scope_risk == "underspecified":
        return ("Claim scope is underspecified relative to the level of paper ambition.", 2)
    if role in {"Background", "Field Context"} and has_claim and not has_evidence:
        return ("Context paragraph introduces an unsupported claim.", 3)
    if has_claim and claim_text and len(claim_text.split()) < 6:
        return ("Claim is too vague to guide revision work.", 3)
    return ("No major issue detected.", 4)


def build_logic_map(
    paper_raw: dict,
    section_roles: dict,
    claims: dict,
    evidence_map: dict,
    nature_quality_rubric: dict,
    llm_client=None,
) -> dict:
    role_by_paragraph = {item["paragraph_id"]: item for item in section_roles["items"]}
    claim_by_paragraph = {item["paragraph_id"]: item for item in claims["items"]}
    evidence_by_paragraph = {item["paragraph_id"]: item for item in evidence_map["items"]}
    items: list[dict] = []
    previous_role: str | None = None

    for section in paper_raw["sections"]:
        for paragraph in section["paragraphs"]:
            role_item = role_by_paragraph[paragraph["id"]]
            claim_item = claim_by_paragraph[paragraph["id"]]
            evidence_item = evidence_by_paragraph[paragraph["id"]]
            claim_scope_risk = _detect_claim_scope_risk(
                role=role_item["role"],
                claim_text=claim_item["claim_text"],
                has_evidence=evidence_item["has_evidence"],
            )
            significance_risk = _detect_significance_risk(
                role=role_item["role"],
                text=paragraph["text"],
                has_claim=claim_item["has_claim"],
                has_evidence=evidence_item["has_evidence"],
            )
            narrative_link_issue = _detect_narrative_link_issue(
                previous_role=previous_role,
                role=role_item["role"],
                has_claim=claim_item["has_claim"],
            )
            vulnerability, priority = _detect_vulnerability(
                role=role_item["role"],
                has_claim=claim_item["has_claim"],
                claim_text=claim_item["claim_text"],
                has_evidence=evidence_item["has_evidence"],
                claim_scope_risk=claim_scope_risk,
                narrative_link_issue=narrative_link_issue,
                significance_risk=significance_risk,
            )
            issue_type = _detect_issue_type(
                role=role_item["role"],
                has_claim=claim_item["has_claim"],
                has_evidence=evidence_item["has_evidence"],
                claim_scope_risk=claim_scope_risk,
                narrative_link_issue=narrative_link_issue,
                significance_risk=significance_risk,
            )
            items.append(
                {
                    "paragraph_id": paragraph["id"],
                    "section": section["title"],
                    "role": role_item["role"],
                    "claim": {
                        "has_claim": claim_item["has_claim"],
                        "claim_text": claim_item["claim_text"],
                        "status": claim_item["status"],
                    },
                    "evidence": {
                        "has_evidence": evidence_item["has_evidence"],
                        "items": evidence_item["evidence_items"],
                    },
                    "issue_type": issue_type,
                    "nature_quality_dimensions": _dimension_flags(
                        role=role_item["role"],
                        has_claim=claim_item["has_claim"],
                        has_evidence=evidence_item["has_evidence"],
                        claim_scope_risk=claim_scope_risk,
                        narrative_link_issue=narrative_link_issue,
                        significance_risk=significance_risk,
                    ),
                    "claim_scope_risk": claim_scope_risk,
                    "narrative_link_issue": narrative_link_issue,
                    "significance_risk": significance_risk,
                    "logical_vulnerability": vulnerability,
                    "priority": priority,
                    "source_text": paragraph["text"],
                }
            )
            previous_role = role_item["role"]

    return {
        "document_name": paper_raw["document_name"],
        "rubric_name": nature_quality_rubric["rubric_name"],
        "item_count": len(items),
        "items": items,
    }
