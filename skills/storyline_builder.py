"""Build a lightweight manuscript-level storyline artifact."""

from __future__ import annotations

import re


def _split_sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]


def _extract_problem_text(text: str) -> str:
    sentences = _split_sentences(text)
    return sentences[0] if sentences else text


def _extract_gap_text(text: str, claim_text: str | None) -> str:
    if claim_text:
        return claim_text
    sentences = _split_sentences(text)
    for sentence in sentences:
        lower_sentence = sentence.lower()
        if any(marker in lower_sentence for marker in ("however", "few studies", "lack", "limited", "gap", "challenge")):
            return sentence
    return sentences[-1] if sentences else text


def _detect_significance_risk(logic_map: dict | None) -> str:
    if not logic_map:
        return "unknown"
    for item in logic_map["items"]:
        if item["role"] == "Discussion":
            return item.get("significance_risk", "unknown")
    return "missing_discussion_signal"


def build_storyline(paper_raw: dict, section_roles: dict, claims: dict, logic_map: dict | None = None) -> dict:
    role_by_paragraph = {item["paragraph_id"]: item for item in section_roles["items"]}
    claim_by_paragraph = {item["paragraph_id"]: item for item in claims["items"]}

    problem_candidates: list[str] = []
    gap_candidates: list[str] = []
    contribution_candidates: list[str] = []
    result_candidates: list[str] = []
    contribution_seen = False

    for section in paper_raw["sections"]:
        for paragraph in section["paragraphs"]:
            paragraph_id = paragraph["id"]
            role = role_by_paragraph[paragraph_id]["role"]
            claim_item = claim_by_paragraph[paragraph_id]
            text = paragraph["text"]
            section_title = section["title"].lower()

            if role in {"Background", "Field Context"} and not contribution_seen and (
                "intro" in section_title or len(problem_candidates) == 0
            ):
                problem_candidates.append(_extract_problem_text(text))
            if role == "Gap Identification":
                if not problem_candidates:
                    problem_candidates.append(_extract_problem_text(text))
                gap_candidates.append(_extract_gap_text(text, claim_item["claim_text"]))
            if role == "Contribution":
                contribution_seen = True
                contribution_candidates.append(claim_item["claim_text"] or text)
            if role == "Result Interpretation":
                result_candidates.append(claim_item["claim_text"] or text)

    logic_items = logic_map["items"] if logic_map else []
    main_risks = [
        {
            "paragraph_id": item["paragraph_id"],
            "issue_type": item["issue_type"],
            "problem": item["logical_vulnerability"],
        }
        for item in logic_items
        if item["priority"] <= 2
    ]

    main_problem = (
        problem_candidates[0]
        if problem_candidates
        else "Main problem not clearly extracted."
    )
    main_gap = gap_candidates[-1] if gap_candidates else "Main gap not clearly extracted."
    core_contribution = (
        contribution_candidates[0] if contribution_candidates else "Core contribution not clearly extracted."
    )

    return {
        "document_name": paper_raw["document_name"],
        "main_problem": main_problem,
        "main_gap": main_gap,
        "core_contribution": core_contribution,
        "supporting_results": result_candidates,
        "main_risks": main_risks,
        "significance_risk": _detect_significance_risk(logic_map),
    }
