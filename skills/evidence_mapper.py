"""Map paragraph claims to simple evidence signals."""

from __future__ import annotations

import re


CITATION_PATTERN = re.compile(r"\[[0-9,\-\s]+\]|\([A-Z][A-Za-z]+(?: et al\.)?,\s*\d{4}\)")
FIGURE_TABLE_PATTERN = re.compile(r"\b(?:Figure|Fig\.|Table|Tab\.)\s*\d+\b")
RESULT_MARKERS = (
    "we show",
    "we find",
    "results indicate",
    "results show",
    "accuracy",
    "f1",
    "improves",
    "outperforms",
    "significant",
)


def _collect_evidence(text: str) -> list[dict]:
    evidence_items: list[dict] = []

    for match in CITATION_PATTERN.findall(text):
        evidence_items.append({"type": "citation", "value": match})
    for match in FIGURE_TABLE_PATTERN.findall(text):
        evidence_items.append({"type": "figure_table", "value": match})

    lower_text = text.lower()
    if any(marker in lower_text for marker in RESULT_MARKERS):
        evidence_items.append(
            {
                "type": "explicit_result",
                "value": "paragraph contains an explicit result-oriented statement",
            }
        )

    return evidence_items


def map_evidence(paper_raw: dict, claims: dict, llm_client=None) -> dict:
    claim_by_paragraph = {item["paragraph_id"]: item for item in claims["items"]}
    items: list[dict] = []

    for section in paper_raw["sections"]:
        for paragraph in section["paragraphs"]:
            claim_item = claim_by_paragraph[paragraph["id"]]
            evidence_items = _collect_evidence(paragraph["text"])
            items.append(
                {
                    "paragraph_id": paragraph["id"],
                    "section": section["title"],
                    "claim_text": claim_item["claim_text"],
                    "has_claim": claim_item["has_claim"],
                    "has_evidence": bool(evidence_items),
                    "evidence_items": evidence_items,
                    "source_text": paragraph["text"],
                }
            )

    return {
        "document_name": paper_raw["document_name"],
        "supported_evidence_types": [
            "citation",
            "figure_table",
            "explicit_result",
        ],
        "item_count": len(items),
        "items": items,
    }
