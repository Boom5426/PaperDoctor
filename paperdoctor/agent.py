"""Minimal agent facade for the PaperDoctor pipeline."""

from pathlib import Path

from paperdoctor.pipeline import run_pipeline


def run(
    document_path: str | Path,
    journal_name: str | None = None,
    scope: str = "full",
    refresh: bool = False,
) -> dict:
    return run_pipeline(
        Path(document_path),
        journal_name=journal_name,
        scope=scope,
        refresh=refresh,
    )
