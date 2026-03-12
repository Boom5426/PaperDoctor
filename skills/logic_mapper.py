"""Build a compact claim-centered logic map from confirmed anchors and evidence support."""

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


def _token_set(text: str | None) -> set[str]:
    normalized = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    return {token for token in normalized.split() if len(token) > 3}


def _normalize_text(text: str | None) -> str:
    return " ".join(re.sub(r"[^a-z0-9\s]", " ", (text or "").lower()).split()[:8])


def _broad_claim(claim_text: str | None) -> bool:
    lower_text = (claim_text or "").lower()
    return any(marker in lower_text for marker in ("all", "always", "universal", "prove", "dramatic", "fundamental"))


def _claim_scope_risk(claim_text: str | None, support_level: str) -> str:
    if _broad_claim(claim_text) and support_level != "strong":
        return "overclaim"
    if support_level in {"weak", "unsupported"}:
        return "underspecified"
    return "supported"


def _dimension_flags(issue_type: str, support_level: str, claim_scope_risk: str, narrative_link_issue: str) -> dict:
    return {
        "gap_clarity": issue_type != "gap",
        "contribution_sharpness": issue_type != "contribution",
        "claim_evidence_alignment": support_level in {"strong", "partial"},
        "claim_scope_control": claim_scope_risk != "overclaim",
        "validation_rigor": support_level == "strong" or issue_type != "validation",
        "narrative_coherence": narrative_link_issue == "clear",
        "significance_framing": True,
    }


def _narrative_link_issue(claim_label: str, role: str, support_level: str) -> str:
    if claim_label == "primary" and role not in {"objective", "contribution", "result", "interpretation"}:
        return "primary_claim_attached_to_weak_role"
    if role in {"transition", "non_core"}:
        return "claim_sits_in_non_core_paragraph"
    if role == "interpretation" and support_level in {"weak", "unsupported"}:
        return "interpretation_without_direct_support"
    return "clear"


def _build_claim_issue(
    claim: dict,
    evidence_entry: dict,
    role_item: dict | None,
) -> dict | None:
    role = role_item["role"] if role_item else "non_core"
    paragraph_id = role_item["paragraph_id"] if role_item else claim["paragraph_id"]
    section = role_item["section"] if role_item else claim["section"]
    support_level = evidence_entry["support_level"]
    claim_scope_risk = _claim_scope_risk(claim["text"], support_level)
    narrative_link_issue = _narrative_link_issue(claim["label"], role, support_level)

    issue_type = None
    problem = None
    priority = 3
    if claim["label"] == "primary" and support_level == "unsupported":
        issue_type = "evidence"
        problem = "A confirmed primary claim is currently unsupported by local evidence spans."
        priority = 1
    elif claim["label"] == "primary" and support_level in {"weak", "partial"}:
        issue_type = "validation"
        problem = "A confirmed primary claim has weak support and lacks convincing validation anchors."
        priority = 1 if support_level == "weak" else 2
    elif claim_scope_risk == "overclaim":
        issue_type = "scope"
        problem = "The claim scope appears broader than the linked evidence can justify."
        priority = 1
    elif claim["label"] == "primary" and role not in {"objective", "contribution"}:
        issue_type = "contribution"
        problem = "A confirmed primary claim is not positioned clearly as the paper's central contribution."
        priority = 2
    elif narrative_link_issue != "clear":
        issue_type = "narrative"
        problem = "The confirmed claim is attached to a weak rhetorical position in the current narrative."
        priority = 2

    if issue_type not in REAL_ISSUE_TYPES:
        return None

    source_span = evidence_entry["evidence_spans"][0]["span_text"] if evidence_entry["evidence_spans"] else claim["text"]
    evidence_items = []
    if evidence_entry["evidence_type"] and evidence_entry["evidence_spans"]:
        evidence_items = [
            {
                "type": evidence_type,
                "value": span["anchor_text"] or span["span_text"][:120],
            }
            for evidence_type in evidence_entry["evidence_type"][:1]
            for span in evidence_entry["evidence_spans"][:1]
        ]

    return {
        "issue_id": f"issue_{claim['claim_id']}",
        "paragraph_id": paragraph_id,
        "section": section,
        "role": role,
        "claim": {
            "has_claim": True,
            "claim_text": claim["text"],
            "status": claim["label"],
        },
        "evidence": {
            "has_evidence": support_level != "unsupported",
            "items": evidence_items,
            "support_level": support_level,
            "missing_expected_evidence": evidence_entry["missing_expected_evidence"],
            "rationale": evidence_entry["rationale"],
        },
        "issue_type": issue_type,
        "nature_quality_dimensions": _dimension_flags(issue_type, support_level, claim_scope_risk, narrative_link_issue),
        "claim_scope_risk": claim_scope_risk,
        "narrative_link_issue": narrative_link_issue,
        "significance_risk": "not_applicable",
        "logical_vulnerability": problem,
        "priority": priority,
        "source_text": source_span,
        "theme_key": _normalize_text(claim["text"]),
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
    del claims, llm_client
    role_by_paragraph = {item["paragraph_id"]: item for item in section_roles["items"]}
    evidence_by_claim = {item["claim_id"]: item for item in evidence_map["items"]}
    items: list[dict] = []
    seen_signatures: set[tuple[str, str, str]] = set()

    gap_tokens = _token_set(storyline_confirmed.get("gap"))
    contribution_tokens = _token_set(storyline_confirmed.get("contribution"))
    has_gap_anchor = any(
        item["role"] == "gap" and len(_token_set(item["source_text"]) & gap_tokens) >= 2
        for item in section_roles["items"]
    )
    if not has_gap_anchor and gap_tokens:
        items.append(
            {
                "issue_id": "issue_gap_anchor",
                "paragraph_id": "storyline_gap",
                "section": "Introduction",
                "role": "gap",
                "claim": {
                    "has_claim": True,
                    "claim_text": storyline_confirmed.get("gap"),
                    "status": "confirmed_gap",
                },
                "evidence": {
                    "has_evidence": False,
                    "items": [],
                    "support_level": "unsupported",
                    "missing_expected_evidence": ["explicit unresolved gap statement"],
                    "rationale": "Confirmed gap is not cleanly grounded in an explicit gap paragraph.",
                },
                "issue_type": "gap",
                "nature_quality_dimensions": _dimension_flags("gap", "unsupported", "supported", "clear"),
                "claim_scope_risk": "supported",
                "narrative_link_issue": "clear",
                "significance_risk": "not_applicable",
                "logical_vulnerability": "The paper-level gap is confirmed by the author but not stated cleanly in the draft.",
                "priority": 2,
                "source_text": storyline_confirmed.get("gap", ""),
                "theme_key": _normalize_text(storyline_confirmed.get("gap")),
            }
        )

    has_contribution_anchor = any(
        item["role"] in {"objective", "contribution"} and len(_token_set(item["source_text"]) & contribution_tokens) >= 2
        for item in section_roles["items"]
    )
    if not has_contribution_anchor and contribution_tokens:
        items.append(
            {
                "issue_id": "issue_contribution_anchor",
                "paragraph_id": "storyline_contribution",
                "section": "Introduction",
                "role": "contribution",
                "claim": {
                    "has_claim": True,
                    "claim_text": storyline_confirmed.get("contribution"),
                    "status": "confirmed_contribution",
                },
                "evidence": {
                    "has_evidence": True,
                    "items": [],
                    "support_level": "partial",
                    "missing_expected_evidence": [],
                    "rationale": "Contribution is confirmed but not sharply placed in a contribution paragraph.",
                },
                "issue_type": "contribution",
                "nature_quality_dimensions": _dimension_flags("contribution", "partial", "supported", "clear"),
                "claim_scope_risk": "supported",
                "narrative_link_issue": "clear",
                "significance_risk": "not_applicable",
                "logical_vulnerability": "The confirmed core contribution is not positioned clearly in a dedicated objective or contribution paragraph.",
                "priority": 2,
                "source_text": storyline_confirmed.get("contribution", ""),
                "theme_key": _normalize_text(storyline_confirmed.get("contribution")),
            }
        )

    for claim in core_claims_confirmed["items"]:
        evidence_entry = evidence_by_claim.get(claim["claim_id"])
        if not evidence_entry:
            continue
        role_item = role_by_paragraph.get(claim["paragraph_id"])
        issue = _build_claim_issue(claim, evidence_entry, role_item)
        if not issue:
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
