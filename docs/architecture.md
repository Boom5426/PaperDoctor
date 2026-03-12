# PaperDoctor Architecture

This stage implements a minimal pipeline with explicit intermediate cognition layers, a unified Nature-quality rubric, a lightweight journal profile layer, and a centralized LLM client entry:

`docx -> paper_raw.json -> section_roles.json -> claims.json -> evidence_map.json -> nature_quality_rubric.json -> logic_map.json -> storyline.json -> journal_profile.json -> revision_report.md`

The current version is heuristic-first for stability, but all future API-backed calls are expected to flow through `paperdoctor/llm/client.py`.

## Product Positioning

Current primary product/demo positioning:

- Nature-family paper diagnosis and revision
- Target state: help a draft reach Nature-family review expectations rather than optimize for one exact sub-journal

Architecture stance:

- The pipeline is not hard-coded to Nature-family only.
- A unified Nature-quality rubric drives diagnosis.
- A lightweight profile layer can still contextualize reporting without becoming a weighting system.

## Module Split

`skills/parse_docx.py`

- Input: `.docx`
- Output: `paper_raw.json`
- Responsibility: parse section and paragraph structure

`skills/section_role_annotator.py`

- Input: `paper_raw.json`
- Output: `section_roles.json`
- Responsibility: assign rhetorical role per paragraph

`skills/claim_extractor.py`

- Input: `paper_raw.json`
- Output: `claims.json`
- Responsibility: extract explicit claim or mark claim absence

`skills/evidence_mapper.py`

- Input: `paper_raw.json` + `claims.json`
- Output: `evidence_map.json`
- Responsibility: detect citation / figure-table / explicit-result evidence

`skills/logic_mapper.py`

- Input: parsed text + roles + claims + evidence
- Output: `logic_map.json`
- Responsibility: integrate the intermediate cognition layers into one logic diagnosis view, including scope risk and narrative-link diagnostics

`skills/nature_quality_rubric.py`

- Input: none
- Output: `nature_quality_rubric.json`
- Responsibility: define the unified Nature-family quality dimensions used by diagnosis and revision planning

`skills/storyline_builder.py`

- Input: parsed text + roles + claims + logic map
- Output: `storyline.json`
- Responsibility: extract a lightweight manuscript-level main-problem / gap / contribution / risks artifact

`skills/journal_adapter.py`

- Input: target journal name
- Output: `journal_profile.json`
- Responsibility: provide lightweight Nature-family reporting context without sub-journal weighting

`skills/revision_planner.py`

- Input: `logic_map.json` + `journal_profile.json`
- Output: `revision_report.md`
- Responsibility: convert logic issues into a journal-aware submission diagnosis report

`paperdoctor/llm/client.py`

- Input: environment variables or `.env`
- Output: a single OpenAI-compatible client wrapper
- Responsibility: centralize API configuration and prevent direct provider calls from being scattered across skills
