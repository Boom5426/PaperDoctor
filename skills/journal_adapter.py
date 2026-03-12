"""Lightweight Nature-family profile adapter."""

from __future__ import annotations


DEFAULT_JOURNAL = "Nature-family"


NATURE_FAMILY_PROFILE = {
    "journal": "Nature-family",
    "positioning": "Assess whether the manuscript approaches Nature-family review expectations, not whether it matches a single sub-journal template.",
    "expects": [
        "A sharply stated gap and contribution that matter beyond routine incremental improvement.",
        "Claims that stay proportional to the evidence and are supported by explicit validation anchors.",
        "A coherent narrative from field problem to gap to contribution to result to significance.",
    ],
    "common_failures": [
        "The manuscript describes a pipeline or finding but does not make the main methodological or conceptual advance explicit.",
        "The strongest claims are not tied to clear evidence, controls, or benchmark logic.",
        "The introduction and discussion do not make significance legible to a broad high-impact readership.",
    ],
    "revision_focus": [
        "gap",
        "contribution",
        "evidence",
        "scope",
        "validation",
        "narrative",
        "significance",
    ],
}


def get_journal_profile(journal_name: str | None = None) -> dict:
    requested = journal_name or DEFAULT_JOURNAL
    if requested not in {DEFAULT_JOURNAL, "Nature Methods", "Nature Communications", "Nature Biotechnology", "Nature Machine Intelligence"}:
        raise ValueError(
            "Unsupported journal target. Use 'Nature-family' or a Nature-family alias such as 'Nature Methods'."
        )
    return NATURE_FAMILY_PROFILE
