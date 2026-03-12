"""Pipeline orchestration for the minimal runnable version."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from paperdoctor.llm import load_llm_client
from skills.claim_extractor import extract_claims
from skills.evidence_mapper import map_evidence
from skills.journal_adapter import get_journal_profile
from skills.logic_mapper import build_logic_map
from skills.nature_quality_rubric import get_nature_quality_rubric
from skills.parse_docx import parse_docx
from skills.revision_planner import build_revision_plan, render_revision_report
from skills.section_role_annotator import annotate_section_roles
from skills.storyline_builder import build_storyline


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "outputs"
SCHEMA_DIR = ROOT_DIR / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_pipeline(document_path: Path, journal_name: str | None = None) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    llm_client = load_llm_client()

    paper_raw = parse_docx(document_path)
    paper_raw_path = OUTPUT_DIR / "paper_raw.json"
    _write_json(paper_raw_path, paper_raw)

    section_roles = annotate_section_roles(paper_raw, llm_client=llm_client)
    section_roles_path = OUTPUT_DIR / "section_roles.json"
    _write_json(section_roles_path, section_roles)

    claims = extract_claims(paper_raw, llm_client=llm_client)
    claims_path = OUTPUT_DIR / "claims.json"
    _write_json(claims_path, claims)

    evidence_map = map_evidence(paper_raw, claims, llm_client=llm_client)
    evidence_map_path = OUTPUT_DIR / "evidence_map.json"
    _write_json(evidence_map_path, evidence_map)

    nature_quality_rubric = get_nature_quality_rubric()
    nature_quality_rubric_path = OUTPUT_DIR / "nature_quality_rubric.json"
    _write_json(nature_quality_rubric_path, nature_quality_rubric)

    logic_map = build_logic_map(
        paper_raw,
        section_roles,
        claims,
        evidence_map,
        nature_quality_rubric,
        llm_client=llm_client,
    )
    validate(instance=logic_map, schema=_load_schema("logic_map_schema.json"))
    logic_map_path = OUTPUT_DIR / "logic_map.json"
    _write_json(logic_map_path, logic_map)

    storyline = build_storyline(paper_raw, section_roles, claims, logic_map)
    storyline_path = OUTPUT_DIR / "storyline.json"
    _write_json(storyline_path, storyline)

    journal_profile = get_journal_profile(journal_name)
    journal_profile_path = OUTPUT_DIR / "journal_profile.json"
    _write_json(journal_profile_path, journal_profile)

    revision_plan = build_revision_plan(
        logic_map,
        journal_profile,
        nature_quality_rubric,
        storyline,
        llm_client=llm_client,
    )
    validate(instance=revision_plan, schema=_load_schema("revision_schema.json"))
    revision_report_path = OUTPUT_DIR / "revision_report.md"
    revision_report_path.write_text(
        render_revision_report(revision_plan, journal_profile),
        encoding="utf-8",
    )

    return {
        "paper_raw_path": str(paper_raw_path),
        "section_roles_path": str(section_roles_path),
        "claims_path": str(claims_path),
        "evidence_map_path": str(evidence_map_path),
        "nature_quality_rubric_path": str(nature_quality_rubric_path),
        "logic_map_path": str(logic_map_path),
        "storyline_path": str(storyline_path),
        "journal_profile_path": str(journal_profile_path),
        "revision_report_path": str(revision_report_path),
        "logic_issue_count": len(logic_map["items"]),
        "revision_item_count": len(revision_plan["items"]),
        "llm_configured": llm_client.is_configured,
    }
