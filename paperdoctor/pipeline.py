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
from skills.hitl_alignment import (
    build_core_claim_candidates,
    build_storyline_draft,
    run_hitl_alignment_checkpoint,
)
from skills.issue_clusterer import build_issue_clusters
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


class PipelineLogger:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def info(self, message: str) -> None:
        print(f"[PaperDoctor] {message}")

    def stage_start(self, name: str) -> None:
        self.info(f"{name}...")

    def stage_done(self, name: str, summary: str | None = None) -> None:
        suffix = f" | {summary}" if summary else ""
        self.info(f"{name} complete{suffix}")

    def detail(self, message: str) -> None:
        if self.verbose:
            self.info(message)


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
    logger: PipelineLogger,
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
) -> tuple[dict, Path, str]:
    path = _artifact_path(name, scope, extension)
    if _can_reuse_artifact(
        manifest,
        name=name,
        scope=scope,
        path=path,
        doc_hash=doc_hash,
        refresh=refresh,
    ):
        logger.detail(f"reuse {name} ({scope}) -> {path.name}")
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
        return payload, path, "reused"

    logger.detail(f"recompute {name} ({scope}) -> {path.name}")
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
    return payload, path, "recomputed"


def run_pipeline(
    document_path: Path,
    journal_name: str | None = None,
    scope: str = "full",
    refresh: bool = False,
    verbose: bool = False,
) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if scope not in SUPPORTED_SCOPES:
        raise ValueError(f"Unsupported scope '{scope}'. Supported scopes: {sorted(SUPPORTED_SCOPES)}")

    logger = PipelineLogger(verbose=verbose)
    llm_client = load_llm_client()
    logger.stage_start("Loading / reusing cached artifacts")
    manifest = _load_manifest()
    doc_hash = _compute_doc_hash(document_path)
    paper_id = _paper_id(document_path, doc_hash)
    logger.stage_done(
        "Loading / reusing cached artifacts",
        f"paper_id={paper_id} | scope={scope} | refresh={refresh} | llm_configured={llm_client.is_configured}",
    )

    logger.stage_start("Parsing DOCX")
    paper_raw, paper_raw_path, paper_raw_status = _prepare_artifact(
        logger,
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
    logger.stage_done(
        "Parsing DOCX",
        (
            f"{paper_raw_status} | sections={paper_raw['section_count']} | "
            f"paragraphs={paper_raw['paragraph_count']} | output={paper_raw_path.name}"
        ),
    )

    scoped_paper_raw = _filter_paper_raw_by_scope(paper_raw, scope)
    logger.detail(
        f"scope filter ({scope}) -> sections={scoped_paper_raw['section_count']} | paragraphs={scoped_paper_raw['paragraph_count']}"
    )

    logger.stage_start("Section role annotation")
    section_roles, section_roles_path, section_roles_status = _prepare_artifact(
        logger,
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
    logger.stage_done(
        "Section role annotation",
        f"{section_roles_status} | paragraphs={section_roles['item_count']} | output={section_roles_path.name}",
    )

    logger.stage_start("Claim extraction")
    claims, claims_path, claims_status = _prepare_artifact(
        logger,
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
    extracted_claims = sum(1 for item in claims["items"] if item["has_claim"])
    logger.stage_done(
        "Claim extraction",
        f"{claims_status} | extracted_claims={extracted_claims}/{claims['item_count']} | output={claims_path.name}",
    )

    logger.stage_start("Evidence mapping")
    evidence_map, evidence_map_path, evidence_status = _prepare_artifact(
        logger,
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
    evidence_supported = sum(1 for item in evidence_map["items"] if item["has_evidence"])
    logger.stage_done(
        "Evidence mapping",
        f"{evidence_status} | evidence_supported={evidence_supported}/{evidence_map['item_count']} | output={evidence_map_path.name}",
    )

    logger.stage_start("Building storyline draft")
    storyline_draft, storyline_draft_path, storyline_draft_status = _prepare_artifact(
        logger,
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="storyline_draft",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=lambda: build_storyline_draft(scoped_paper_raw, section_roles, claims, evidence_map),
    )
    logger.stage_done(
        "Building storyline draft",
        f"{storyline_draft_status} | output={storyline_draft_path.name}",
    )

    logger.stage_start("Building core claims draft")
    core_claims_draft, core_claims_draft_path, core_claims_draft_status = _prepare_artifact(
        logger,
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="core_claims_draft",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=lambda: build_core_claim_candidates(scoped_paper_raw, section_roles, claims),
    )
    logger.stage_done(
        "Building core claims draft",
        f"{core_claims_draft_status} | candidates={core_claims_draft['item_count']} | output={core_claims_draft_path.name}",
    )

    logger.stage_start("HITL alignment checkpoint")
    confirmed_cache: dict[str, dict] = {}

    def _run_hitl_once() -> tuple[dict, dict]:
        if "storyline_confirmed" not in confirmed_cache or "core_claims_confirmed" not in confirmed_cache:
            storyline_confirmed_value, core_claims_confirmed_value = run_hitl_alignment_checkpoint(
                storyline_draft,
                core_claims_draft,
            )
            confirmed_cache["storyline_confirmed"] = storyline_confirmed_value
            confirmed_cache["core_claims_confirmed"] = core_claims_confirmed_value
        return confirmed_cache["storyline_confirmed"], confirmed_cache["core_claims_confirmed"]

    def _confirm_storyline() -> dict:
        storyline_confirmed, _ = _run_hitl_once()
        return storyline_confirmed

    def _confirm_core_claims() -> dict:
        _, core_claims_confirmed = _run_hitl_once()
        return core_claims_confirmed

    storyline_confirmed, storyline_confirmed_path, storyline_confirmed_status = _prepare_artifact(
        logger,
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="storyline_confirmed",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=_confirm_storyline,
    )
    core_claims_confirmed, core_claims_confirmed_path, core_claims_confirmed_status = _prepare_artifact(
        logger,
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="core_claims_confirmed",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=_confirm_core_claims,
    )
    logger.stage_done(
        "HITL alignment checkpoint",
        (
            f"storyline={storyline_confirmed_status} | core_claims={core_claims_confirmed_status} | "
            f"confirmed_claims={core_claims_confirmed['item_count']} | outputs={storyline_confirmed_path.name},{core_claims_confirmed_path.name}"
        ),
    )

    logger.stage_start("Loading Nature-quality rubric")
    nature_quality_rubric, nature_quality_rubric_path, rubric_status = _prepare_artifact(
        logger,
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
    logger.stage_done(
        "Loading Nature-quality rubric",
        f"{rubric_status} | dimensions={len(nature_quality_rubric['dimensions'])} | output={nature_quality_rubric_path.name}",
    )

    logger.stage_start("Building logic map")
    logic_map, logic_map_path, logic_map_status = _prepare_artifact(
        logger,
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
            storyline_confirmed,
            core_claims_confirmed,
            llm_client=llm_client,
        ),
        validate_schema="logic_map_schema.json",
    )
    actionable_logic_items = sum(1 for item in logic_map["items"] if item["priority"] < 4)
    logger.stage_done(
        "Building logic map",
        f"{logic_map_status} | items={logic_map['item_count']} | actionable={actionable_logic_items} | output={logic_map_path.name}",
    )

    logger.stage_start("Clustering issues")
    issue_clusters, issue_clusters_path, issue_clusters_status = _prepare_artifact(
        logger,
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="issue_clusters",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=lambda: build_issue_clusters(logic_map),
        validate_schema="issue_clusters_schema.json",
    )
    logger.stage_done(
        "Clustering issues",
        f"{issue_clusters_status} | clusters={issue_clusters['item_count']} | output={issue_clusters_path.name}",
    )

    logger.stage_start("Building storyline")
    storyline, storyline_path, storyline_status = _prepare_artifact(
        logger,
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="storyline",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=lambda: build_storyline(
            scoped_paper_raw,
            section_roles,
            claims,
            issue_clusters,
            storyline_confirmed,
            core_claims_confirmed,
        ),
    )
    logger.stage_done(
        "Building storyline",
        f"{storyline_status} | main_risks={len(storyline['main_risks'])} | output={storyline_path.name}",
    )

    logger.stage_start("Loading journal profile")
    journal_profile, journal_profile_path, journal_profile_status = _prepare_artifact(
        logger,
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
    logger.stage_done(
        "Loading journal profile",
        f"{journal_profile_status} | journal={journal_profile['journal']} | output={journal_profile_path.name}",
    )

    logger.stage_start("Generating revision report")
    revision_plan, revision_plan_path, revision_plan_status = _prepare_artifact(
        logger,
        manifest,
        paper_id=paper_id,
        source_docx=document_path,
        doc_hash=doc_hash,
        name="revision_plan",
        scope=scope,
        extension="json",
        refresh=refresh,
        build_fn=lambda: build_revision_plan(
            issue_clusters,
            journal_profile,
            nature_quality_rubric,
            storyline,
            llm_client=llm_client,
        ),
        validate_schema="revision_schema.json",
    )

    revision_report_payload, revision_report_path, revision_report_status = _prepare_artifact(
        logger,
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
    logger.stage_done(
        "Generating revision report",
        (
            f"plan={revision_plan_status} | report={revision_report_status} | "
            f"revision_items={revision_plan['item_count']} | output={revision_report_path.name}"
        ),
    )

    artifacts = [
        ("paper_raw", paper_raw_status, paper_raw_path.name),
        ("section_roles", section_roles_status, section_roles_path.name),
        ("claims", claims_status, claims_path.name),
        ("evidence_map", evidence_status, evidence_map_path.name),
        ("storyline_draft", storyline_draft_status, storyline_draft_path.name),
        ("core_claims_draft", core_claims_draft_status, core_claims_draft_path.name),
        ("storyline_confirmed", storyline_confirmed_status, storyline_confirmed_path.name),
        ("core_claims_confirmed", core_claims_confirmed_status, core_claims_confirmed_path.name),
        ("nature_quality_rubric", rubric_status, nature_quality_rubric_path.name),
        ("logic_map", logic_map_status, logic_map_path.name),
        ("issue_clusters", issue_clusters_status, issue_clusters_path.name),
        ("storyline", storyline_status, storyline_path.name),
        ("journal_profile", journal_profile_status, journal_profile_path.name),
        ("revision_plan", revision_plan_status, revision_plan_path.name),
        ("revision_report", revision_report_status, revision_report_path.name),
    ]
    logger.stage_start("Writing outputs")
    _save_manifest(manifest)
    session_manifest_path = MANIFEST_PATH
    logger.stage_done(
        "Writing outputs",
        f"manifest={session_manifest_path.name} | outputs_updated={len(artifacts)}",
    )
    reused_artifacts = [name for name, status, _ in artifacts if status == "reused"]
    recomputed_artifacts = [name for name, status, _ in artifacts if status == "recomputed"]
    output_files = [filename for _, _, filename in artifacts] + [session_manifest_path.name]

    return {
        "paper_raw_path": str(paper_raw_path),
        "section_roles_path": str(section_roles_path),
        "claims_path": str(claims_path),
        "evidence_map_path": str(evidence_map_path),
        "storyline_draft_path": str(storyline_draft_path),
        "core_claims_draft_path": str(core_claims_draft_path),
        "storyline_confirmed_path": str(storyline_confirmed_path),
        "core_claims_confirmed_path": str(core_claims_confirmed_path),
        "nature_quality_rubric_path": str(nature_quality_rubric_path),
        "logic_map_path": str(logic_map_path),
        "issue_clusters_path": str(issue_clusters_path),
        "storyline_path": str(storyline_path),
        "journal_profile_path": str(journal_profile_path),
        "revision_report_path": str(revision_report_path),
        "session_manifest_path": str(session_manifest_path),
        "logic_issue_count": len(logic_map["items"]),
        "issue_cluster_count": len(issue_clusters["items"]),
        "revision_item_count": len(revision_plan["items"]),
        "llm_configured": llm_client.is_configured,
        "scope": scope,
        "refresh": refresh,
        "paper_id": paper_id,
        "verbose": verbose,
        "reused_artifacts": reused_artifacts,
        "recomputed_artifacts": recomputed_artifacts,
        "output_files": output_files,
    }
