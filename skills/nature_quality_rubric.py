"""Unified Nature-family quality rubric for manuscript diagnosis."""

from __future__ import annotations


NATURE_QUALITY_RUBRIC = {
    "rubric_name": "Nature-family Quality Rubric",
    "focus": "Assess whether a manuscript approaches Nature-family review expectations rather than a specific sub-journal style.",
    "dimensions": {
        "gap_clarity": "The paper states a concrete unresolved problem or methodological limitation early and unambiguously.",
        "contribution_sharpness": "The core advance is explicit, differentiated, and easy to restate in one sentence.",
        "claim_evidence_alignment": "Major claims are locally anchored to evidence such as figures, benchmarks, controls, or citations.",
        "claim_scope_control": "Claims stay proportional to the evidence and avoid overclaiming or underspecified scope.",
        "validation_rigor": "Method or result claims are supported by sufficiently strong validation, comparison, and control logic.",
        "narrative_coherence": "The manuscript moves clearly from context to gap to contribution to result to implication.",
        "significance_framing": "The manuscript explains why the contribution matters beyond the immediate implementation details.",
    },
}


def get_nature_quality_rubric() -> dict:
    return NATURE_QUALITY_RUBRIC
