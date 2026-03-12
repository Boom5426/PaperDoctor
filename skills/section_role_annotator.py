"""Annotate paragraph-level rhetorical roles from parsed paper content."""

from __future__ import annotations


SUPPORTED_ROLES = (
    "Background",
    "Field Context",
    "Gap Identification",
    "Contribution",
    "Result Interpretation",
    "Discussion",
)

CONTRIBUTION_MARKERS = (
    "we propose",
    "we present",
    "this paper",
    "we introduce",
    "our work",
    "we develop",
)
GAP_MARKERS = (
    "however",
    "few studies",
    "limited",
    "lack",
    "gap",
    "challenge",
    "remains unclear",
)
FIELD_CONTEXT_MARKERS = (
    "widely used",
    "has been studied",
    "is important",
    "has attracted",
    "recent work",
    "prior work",
)
RESULT_MARKERS = (
    "we show",
    "we find",
    "results",
    "experiment",
    "accuracy",
    "improves",
    "outperforms",
)
DISCUSSION_MARKERS = (
    "these findings",
    "these results",
    "can help",
    "suggests",
    "implication",
    "limitation",
)


def _detect_role(section_title: str, text: str) -> str:
    title = section_title.lower()
    content = text.lower()

    if "discussion" in title or "conclusion" in title:
        return "Discussion"
    if "result" in title or "experiment" in title:
        return "Result Interpretation"
    if any(marker in content for marker in DISCUSSION_MARKERS):
        return "Discussion"
    if any(marker in content for marker in GAP_MARKERS):
        return "Gap Identification"
    if any(marker in content for marker in CONTRIBUTION_MARKERS):
        return "Contribution"
    if "intro" in title and any(marker in content for marker in FIELD_CONTEXT_MARKERS):
        return "Field Context"
    if any(marker in content for marker in RESULT_MARKERS):
        return "Result Interpretation"
    return "Background"


def annotate_section_roles(paper_raw: dict, llm_client=None) -> dict:
    items: list[dict] = []

    for section in paper_raw["sections"]:
        for paragraph in section["paragraphs"]:
            items.append(
                {
                    "paragraph_id": paragraph["id"],
                    "section": section["title"],
                    "role": _detect_role(section["title"], paragraph["text"]),
                    "source_text": paragraph["text"],
                }
            )

    return {
        "document_name": paper_raw["document_name"],
        "supported_roles": list(SUPPORTED_ROLES),
        "item_count": len(items),
        "items": items,
    }
