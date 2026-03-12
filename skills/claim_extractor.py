"""Extract paragraph-level claims from parsed paper content."""

from __future__ import annotations

import re


CLAIM_MARKERS = (
    "we propose",
    "we present",
    "we show",
    "we find",
    "this paper",
    "our results",
    "this study",
    "we demonstrate",
    "improves",
    "outperforms",
    "can help",
    "suggests",
)


def _split_sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]


def _find_claim(text: str) -> tuple[bool, str | None, str]:
    sentences = _split_sentences(text)
    for sentence in sentences:
        lower_sentence = sentence.lower()
        if any(marker in lower_sentence for marker in CLAIM_MARKERS):
            return True, sentence, "explicit_marker"
    if len(sentences) == 1 and len(sentences[0].split()) >= 8:
        return False, None, "no_explicit_claim"
    if not sentences:
        return False, None, "empty_paragraph"
    return False, None, "descriptive_paragraph"


def extract_claims(paper_raw: dict, llm_client=None) -> dict:
    items: list[dict] = []

    for section in paper_raw["sections"]:
        for paragraph in section["paragraphs"]:
            has_claim, claim_text, status = _find_claim(paragraph["text"])
            items.append(
                {
                    "paragraph_id": paragraph["id"],
                    "section": section["title"],
                    "has_claim": has_claim,
                    "claim_text": claim_text,
                    "status": status,
                    "source_text": paragraph["text"],
                }
            )

    return {
        "document_name": paper_raw["document_name"],
        "item_count": len(items),
        "items": items,
    }
