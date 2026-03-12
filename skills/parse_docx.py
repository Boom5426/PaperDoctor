"""Parse a DOCX paper into a minimal structured JSON document."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document


HEADING_STYLE_PREFIX = "heading"
REFERENCE_PATTERN = re.compile(
    r"\b(?:Figure|Fig\.|Table|Tab\.)\s*\d+\b|\[[0-9,\-\s]+\]"
)


def _is_heading(paragraph) -> bool:
    style_name = (paragraph.style.name or "").strip().lower()
    text = paragraph.text.strip()
    if not text:
        return False
    if style_name.startswith(HEADING_STYLE_PREFIX):
        return True
    return len(text.split()) <= 8 and text == text.title() and not text.endswith(".")


def _extract_references(text: str) -> list[str]:
    return REFERENCE_PATTERN.findall(text)


def parse_docx(document_path: str | Path) -> dict:
    document_path = Path(document_path)
    document = Document(document_path)

    sections: list[dict] = []
    current_section = {"id": "section_1", "title": "Untitled", "paragraphs": []}
    paragraph_count = 0
    section_count = 1

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        if _is_heading(paragraph):
            if current_section["paragraphs"] or current_section["title"] != "Untitled":
                sections.append(current_section)
            section_count += 1
            current_section = {
                "id": f"section_{section_count}",
                "title": text,
                "paragraphs": [],
            }
            continue

        paragraph_count += 1
        current_section["paragraphs"].append(
            {
                "id": f"p{paragraph_count}",
                "text": text,
                "references": _extract_references(text),
            }
        )

    if current_section["paragraphs"] or not sections:
        sections.append(current_section)

    return {
        "document_name": document_path.name,
        "section_count": len(sections),
        "paragraph_count": paragraph_count,
        "sections": sections,
    }

