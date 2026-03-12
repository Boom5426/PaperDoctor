"""Pipeline orchestration with artifact-first reuse."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
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
MANIFEST_PATH = OUTPUT_DIR / "session_manifest.json"
SUPPORTED_SCOPES = {"full", "abstract", "intro", "results"}


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_doc_hash(document_path: Path) -> str:
    return hashlib.sha256(document_path.read_bytes()).hexdigest()


def _paper_id(document_path: Path, doc_hash: str) -> str:
    return f"{document_path.stem}-{doc_hash[:12]}"


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {"generated_artifacts": {}}
    return _load_json(MANIFEST_PATH)


def _save_manifest(manifest: dict) -> None:
    _write_json(MANIFEST_PATH, manifest)


def _artifact_filename(name: str, scope: str, extension: str) -> str:
    if scope == "full":
        return f"{name}.{extension}"
    return f"{scope}_{name}.{extension}"


def _artifact_path(name: str, scope: str, extension: str) -> Path:
    return OUTPUT_DIR / _artifact_filename(name, scope, extension)


def _artifact_key(name: str, scope: str) -> str:
    return f"{scope}:{name}"


def _update_manifest_artifact(
    manifest: dict,
    *,
    paper_id: str,
    source_docx: Path,
    doc_hash: str,
    name: str,
    scope: str,
    path: Path,
    reused: bool,
    extra: dict | None = None,
) -> None:
    manifest["paper_id"] = paper_id
    manifest["source_docx"] = str(source_docx)
    manifest["doc_hash"] = doc_hash
    manifest["last_run_at"] = _utc_now()
    manifest.setdefault("generated_artifacts", {})
    manifest["generated_artifacts"][_artifact_key(name, scope)] = {
        "name": name,
        "scope": scope,
        "path": str(path),
        "doc_hash": doc_hash,
        "generated_at": _utc_now(),
        "status": "reused" if reused else "recomputed",
        **(extra or {}),
    }


def _can_reuse_artifact(manifest: dict, *, name: str, scope: str, path: Path, doc_hash: str, refresh: bool) -> bool:
    if refresh or not path.exists():
        return False
    artifact = manifest.get("generated_artifacts", {}).get(_artifact_key(name, scope))
    if not artifact:
        return False
    return artifact.get("doc_hash") == doc_hash


def _log(message: str) -> None:
    print(f"[PaperDoctor] {message}")


def _section_matches_scope(title: str, scope: str) -> bool:
    lower_title = title.lower()
    if scope == "full":
        return True
    if scope == "abstract":
        return "abstract" in lower_title
    if scope == "intro":
        return "intro" in lower_title
    if scope == "results":
        return "result" in lower_title or "experiment" in lower_title
    return False


def _filter_paper_raw_by_scope(paper_raw: dict, scope: str) -> dict:
    if scope == "full":
        return paper_raw
    filtered_sections = [
        section
        for section in paper_raw["sections"]
        if _section_matches_scope(section["title"], scope)
    ]
    paragraph_count = sum(len(section["paragraphs"]) for section in filtered_sections)
    return {
        "document_name": paper_raw["document_name"],
        "section_count": len(filtered_sections),
        "paragraph_count": paragraph_count,
        "sections": filtered_sections,
    }


def _prepare_artifact(
    manifest: dict,
    *,
    paper_id: str,
    source_docx: Path,
    doc_hash: str,
    name: str,
    scope: str,
    extension: str,
    refresh: bool,
    build_fn,
    validate_schema: str | None = None,
    extra_manifest: dict | None = None,
) -> tuple[dict, Path, bool]:
    path = _artifact_path(name, scope, extension)
    if _can_reuse_artifact(
        manifest,
        name=name,
        scope=scope,
        path=path,
        doc_hash=doc_hash,
        refresh=refresh,
    ):
        _log(f"reuse {name} ({scope}) -> {path.name}")
        payload = _load_json(path) if extension == "json" else {"path": str(path)}
        _update_manifest_artifact(
            manifest,
            paper_id=paper_id,
            source_docx=source_docx,
            doc_hash=doc_hash,
            name=name,
            scope=scope,
            path=path,
            reused=True,
            extra=extra_manifest,
        )
        return payload, path, True

    _log(f"recompute {name} ({scope}) -> {path.name}")
    payload = build_fn()
    if extension == "json":
        if validate_schema:
            validate(instance=payload, schema=_load_schema(validate_schema))
        _write_json(path, payload)
    else:
        path.write_text(payload, encoding="utf-8")
        payload = {"path": str(path)}
    _update_manifest_artifact(
        manifest,
        paper_id=paper_id,
        source_docx=source_docx,
        doc_hash=doc_hash,
        name=name,
        scope=scope,
        path=path,
        reused=False,
        extra=extra_manifest,
    )
    return payload, path, False


def run_pipeline(
    document_path: Path,
    journal_name: str | None = None,
    scope: str = "full",
    refresh: bool = False,
) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if scope not in SUPPORTED_SCOPES:
        raise ValueError(f"Unsupported scope '{scope}'. Supported scopes: {sorted(SUPPORTED_SCOPES)}")

    llm_client = load_llm_client()
    manifest = _load_manifest()
    doc_hash = _compute_doc_hash(document_path)
    paper_id = _paper_id(document_path, doc_hash)

    paper_raw, paper_raw_path, _ = _prepare_artifact(
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="paper_raw",
        scope="full",
        extension="json",
        refresh=refresh,
        build_fn=lambda: parse_docx(document_path),
    )

    scoped_paper_raw = _filter_paper_raw_by_scope(paper_raw, scope)

    section_roles, section_roles_path, _ = _prepare_artifact(
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="section_roles",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=lambda: annotate_section_roles(scoped_paper_raw, llm_client=llm_client),
    )

    claims, claims_path, _ = _prepare_artifact(
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="claims",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=lambda: extract_claims(scoped_paper_raw, llm_client=llm_client),
    )

    evidence_map, evidence_map_path, _ = _prepare_artifact(
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="evidence_map",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=lambda: map_evidence(scoped_paper_raw, claims, llm_client=llm_client),
    )

    nature_quality_rubric, nature_quality_rubric_path, _ = _prepare_artifact(
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="nature_quality_rubric",
        scope="full",
        extension="json",
        refresh=False,
        build_fn=get_nature_quality_rubric,
    )

    logic_map, logic_map_path, _ = _prepare_artifact(
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="logic_map",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=lambda: build_logic_map(
            scoped_paper_raw,
            section_roles,
            claims,
            evidence_map,
            nature_quality_rubric,
            llm_client=llm_client,
        ),
        validate_schema="logic_map_schema.json",
    )

    storyline, storyline_path, _ = _prepare_artifact(
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="storyline",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=lambda: build_storyline(scoped_paper_raw, section_roles, claims, logic_map),
    )

    journal_profile, journal_profile_path, _ = _prepare_artifact(
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="journal_profile",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=lambda: get_journal_profile(journal_name),
        extra_manifest={"journal_input": journal_name or "Nature-family"},
    )

    revision_plan, _, _ = _prepare_artifact(
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="revision_plan",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=lambda: build_revision_plan(
            logic_map,
            journal_profile,
            nature_quality_rubric,
            storyline,
            llm_client=llm_client,
        ),
        validate_schema="revision_schema.json",
    )

    revision_report_payload, revision_report_path, _ = _prepare_artifact(
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="revision_report",
        scope=scope,
        extension="md",
        refresh=refresh,
        build_fn=lambda: render_revision_report(revision_plan, journal_profile),
        extra_manifest={"journal_input": journal_name or "Nature-family"},
    )

    _save_manifest(manifest)
    session_manifest_path = MANIFEST_PATH

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
        "session_manifest_path": str(session_manifest_path),
        "logic_issue_count": len(logic_map["items"]),
        "revision_item_count": len(revision_plan["items"]),
        "llm_configured": llm_client.is_configured,
        "scope": scope,
        "refresh": refresh,
        "paper_id": paper_id,
    }
