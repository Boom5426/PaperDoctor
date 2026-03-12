"""Build a compact issue-focused logic map from role, claim, and evidence annotations."""

from __future__ import annotations

import re


REAL_ISSUE_TYPES = {
    "evidence",
    "scope",
    "gap",
    "contribution",
    "validation",
    "narrative",
}


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    lowered = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return " ".join(lowered.split()[:10])


def _token_set(text: str | None) -> set[str]:
    normalized = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    return {token for token in normalized.split() if len(token) > 3}


def _build_anchor_context(storyline_confirmed: dict, core_claims_confirmed: dict) -> dict:
    primary_claims = [item["text"] for item in core_claims_confirmed["items"] if item["label"] == "primary"]
    secondary_claims = [item["text"] for item in core_claims_confirmed["items"] if item["label"] == "secondary"]
    return {
        "problem_tokens": _token_set(storyline_confirmed.get("problem")),
        "gap_tokens": _token_set(storyline_confirmed.get("gap")),
        "contribution_tokens": _token_set(storyline_confirmed.get("contribution")),
        "significance_tokens": _token_set(storyline_confirmed.get("significance")),
        "primary_claims": primary_claims,
        "secondary_claims": secondary_claims,
        "primary_claim_tokens": [_token_set(text) for text in primary_claims],
        "secondary_claim_tokens": [_token_set(text) for text in secondary_claims],
    }


def _matches_anchor(text: str | None, token_groups: list[set[str]], minimum_overlap: int = 2) -> bool:
    text_tokens = _token_set(text)
    if not text_tokens:
        return False
    return any(len(text_tokens & token_group) >= minimum_overlap for token_group in token_groups if token_group)


def _detect_claim_scope_risk(role: str, claim_text: str | None, has_evidence: bool) -> str:
    if not claim_text:
        return "supported"
    lower_claim = claim_text.lower()
    broad_markers = ("all", "always", "universally", "solves", "proves", "dramatically")
    if any(marker in lower_claim for marker in broad_markers) and not has_evidence:
        return "overclaim"
    if role in {"Contribution", "Result Interpretation"} and not has_evidence:
        return "underspecified"
    return "supported"


def _detect_narrative_link_issue(previous_role: str | None, role: str, has_claim: bool) -> str:
    if role == "Contribution" and previous_role not in {"Gap Identification", "Field Context"}:
        return "missing_gap_to_contribution_bridge"
    if role == "Result Interpretation" and previous_role not in {"Contribution", "Method", "Background"}:
        return "weak_result_bridge"
    if role == "Discussion" and not has_claim:
        return "weak_implication_bridge"
    return "clear"


def _dimension_flags(
    role: str,
    has_claim: bool,
    has_evidence: bool,
    claim_scope_risk: str,
    narrative_link_issue: str,
) -> dict:
    return {
        "gap_clarity": role == "Gap Identification" and has_claim,
        "contribution_sharpness": role == "Contribution" and has_claim,
        "claim_evidence_alignment": not has_claim or has_evidence,
        "claim_scope_control": claim_scope_risk != "overclaim",
        "validation_rigor": role != "Result Interpretation" or has_evidence,
        "narrative_coherence": narrative_link_issue == "clear",
        "significance_framing": True,
    }


def _issue_from_paragraph(
    *,
    paragraph_id: str,
    section: str,
    role: str,
    claim: dict,
    evidence: dict,
    source_text: str,
    previous_role: str | None,
) -> dict | None:
    has_claim = claim["has_claim"]
    has_evidence = evidence["has_evidence"]
    claim_text = claim["claim_text"]
    claim_scope_risk = _detect_claim_scope_risk(role, claim_text, has_evidence)
    narrative_link_issue = _detect_narrative_link_issue(previous_role, role, has_claim)

    issue_type = None
    problem = None
    priority = 3
    lower_section = section.lower()

    if role == "Contribution" and (not has_claim or not claim_text):
        issue_type = "contribution"
        problem = "The core contribution is not stated clearly enough."
        priority = 1
    elif role == "Contribution" and has_claim and not has_evidence:
        issue_type = "evidence"
        problem = "A core contribution claim is not anchored to evidence."
        priority = 1
    elif (
        role == "Result Interpretation"
        and has_claim
        and not has_evidence
        and ("result" in lower_section or "experiment" in lower_section)
    ):
        issue_type = "validation"
        problem = "A result claim is presented without strong local validation anchors."
        priority = 1
    elif (
        claim_scope_risk == "overclaim"
        and role in {"Contribution", "Result Interpretation", "Discussion"}
        and "data availability" not in lower_section
    ):
        issue_type = "scope"
        problem = "The claim scope appears broader than the evidence shown."
        priority = 1
    elif (
        role == "Gap Identification"
        and not has_claim
        and ("intro" in lower_section or "abstract" in lower_section)
    ):
        issue_type = "gap"
        problem = "The paper signals a gap but does not state the unresolved problem clearly."
        priority = 2
    elif role == "Contribution" and claim_text and len(claim_text.split()) < 8:
        issue_type = "contribution"
        problem = "The contribution is stated too vaguely to anchor the paper-level argument."
        priority = 2
    elif (
        narrative_link_issue != "clear"
        and role in {"Contribution", "Result Interpretation", "Discussion"}
        and ("intro" in lower_section or "discussion" in lower_section)
    ):
        issue_type = "narrative"
        problem = "The narrative transition into this paragraph is weak."
        priority = 2

    if issue_type not in REAL_ISSUE_TYPES:
        return None

    return {
        "issue_id": f"issue_{paragraph_id}",
        "paragraph_id": paragraph_id,
        "section": section,
        "role": role,
        "claim": claim,
        "evidence": evidence,
        "issue_type": issue_type,
        "nature_quality_dimensions": _dimension_flags(
            role=role,
            has_claim=has_claim,
            has_evidence=has_evidence,
            claim_scope_risk=claim_scope_risk,
            narrative_link_issue=narrative_link_issue,
        ),
        "claim_scope_risk": claim_scope_risk,
        "narrative_link_issue": narrative_link_issue,
        "significance_risk": "not_applicable",
        "logical_vulnerability": problem,
        "priority": priority,
        "source_text": source_text,
        "theme_key": _normalize_text(claim_text or source_text),
    }


def build_logic_map(
    paper_raw: dict,
    section_roles: dict,
    claims: dict,
    evidence_map: dict,
    nature_quality_rubric: dict,
    storyline_confirmed: dict,
    core_claims_confirmed: dict,
    llm_client=None,
) -> dict:
    role_by_paragraph = {item["paragraph_id"]: item for item in section_roles["items"]}
    claim_by_paragraph = {item["paragraph_id"]: item for item in claims["items"]}
    evidence_by_paragraph = {item["paragraph_id"]: item for item in evidence_map["items"]}
    items: list[dict] = []
    seen_signatures: set[tuple[str, str, str]] = set()
    previous_role: str | None = None
    anchors = _build_anchor_context(storyline_confirmed, core_claims_confirmed)

    for section in paper_raw["sections"]:
        for paragraph in section["paragraphs"]:
            paragraph_id = paragraph["id"]
            role_item = role_by_paragraph[paragraph_id]
            claim_item = claim_by_paragraph[paragraph_id]
            evidence_item = evidence_by_paragraph[paragraph_id]
            issue = _issue_from_paragraph(
                paragraph_id=paragraph_id,
                section=section["title"],
                role=role_item["role"],
                claim={
                    "has_claim": claim_item["has_claim"],
                    "claim_text": claim_item["claim_text"],
                    "status": claim_item["status"],
                },
                evidence={
                    "has_evidence": evidence_item["has_evidence"],
                    "items": evidence_item["evidence_items"],
                },
                source_text=paragraph["text"],
                previous_role=previous_role,
            )
            previous_role = role_item["role"]
            if not issue:
                continue
            claim_text = claim_item["claim_text"] or paragraph["text"]
            anchored = False
            if issue["issue_type"] == "gap":
                anchored = _matches_anchor(claim_text, [anchors["gap_tokens"], anchors["problem_tokens"]], minimum_overlap=2)
            elif issue["issue_type"] in {"contribution", "evidence", "scope"}:
                anchored = _matches_anchor(
                    claim_text,
                    anchors["primary_claim_tokens"] + [anchors["contribution_tokens"]],
                    minimum_overlap=2,
                )
            elif issue["issue_type"] == "validation":
                anchored = _matches_anchor(
                    claim_text,
                    anchors["primary_claim_tokens"] + anchors["secondary_claim_tokens"],
                    minimum_overlap=2,
                )
            elif issue["issue_type"] == "narrative":
                anchored = role_item["role"] in {"Contribution", "Discussion"} and (
                    _matches_anchor(claim_text, [anchors["contribution_tokens"], anchors["significance_tokens"]], minimum_overlap=1)
                )
            if not anchored:
                continue
            signature = (issue["issue_type"], issue["section"], issue["theme_key"])
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            items.append(issue)

    items.sort(key=lambda item: (item["priority"], item["section"], item["paragraph_id"]))
    return {
        "document_name": paper_raw["document_name"],
        "rubric_name": nature_quality_rubric["rubric_name"],
        "item_count": len(items),
        "items": items,
    }
