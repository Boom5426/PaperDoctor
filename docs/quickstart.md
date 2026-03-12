# Quickstart

## 1. Clone

```bash
git clone https://github.com/Boom5426/PaperDoctor.git
cd PaperDoctor
```

## 2. Install

```bash
pip install -r requirements.txt
```

## 3. Configure `.env`

```bash
cp .env.example .env
```

Then edit `.env` and fill in:

- `PAPERDOCTOR_API_KEY`
- `PAPERDOCTOR_BASE_URL`
- `PAPERDOCTOR_MODEL`
- `PAPERDOCTOR_MAX_TOKENS`
- `PAPERDOCTOR_TIMEOUT`

## 4. Run Demo

```bash
python run_agent.py examples/sample_paper.docx
```

You will now see stage-aware runtime logs such as:

- Parsing DOCX
- Section role annotation
- Claim extraction
- Evidence mapping
- Building logic map
- Building storyline
- Generating revision report
- Writing outputs

Optional:

```bash
python run_agent.py examples/sample_paper.docx --journal "Nature Methods"
```

Scope-based analysis:

```bash
python run_agent.py examples/sample_paper.docx --scope full
python run_agent.py examples/sample_paper.docx --scope intro
python run_agent.py examples/sample_paper.docx --scope results
```

Force refresh:

```bash
python run_agent.py examples/sample_paper.docx --refresh
python run_agent.py examples/sample_paper.docx --scope intro --refresh
```

Verbose mode:

```bash
python run_agent.py examples/sample_paper.docx --verbose
```

## 5. Check Outputs

After the run, PaperDoctor writes:

- `outputs/paper_raw.json`
- `outputs/section_roles.json`
- `outputs/claims.json`
- `outputs/evidence_map.json`
- `outputs/nature_quality_rubric.json`
- `outputs/logic_map.json`
- `outputs/storyline.json`
- `outputs/journal_profile.json`
- `outputs/revision_report.md`
- `outputs/session_manifest.json`

PaperDoctor now uses an artifact-first workflow:

- the `.docx` file is parsed once into `paper_raw.json`
- later runs reuse cached artifacts when the document hash has not changed
- this is especially useful for long papers because later analysis does not need to reread the whole document every time
- when `--scope` is used, scope-specific outputs are written with a prefix such as `intro_logic_map.json`
- runtime logs will show whether an artifact was `reuse` or `recompute`

## 6. Use Your Own Paper

Replace the demo path with your own `.docx`:

```bash
python run_agent.py path/to/your_paper.docx
```

## 7. Troubleshooting

### API key not configured

Symptom:
- `PAPERDOCTOR_API_KEY` missing

Fix:
- copy `.env.example` to `.env`
- set `PAPERDOCTOR_API_KEY`

Note:
- the current pipeline can still run in heuristic mode, but API-backed extensions will not be available
- the current project already supports LLM-enhanced claim extraction and revision planning when `.env` is configured

### `base_url` cannot connect

Symptom:
- request timeout
- connection error

Fix:
- verify `PAPERDOCTOR_BASE_URL`
- confirm your proxy or relay is reachable
- try again with the same `.env`

### `.docx` file not found

Symptom:
- Python raises file not found when running `run_agent.py`

Fix:
- check the input path
- make sure the file extension is `.docx`

### `outputs/` not generated

Symptom:
- run exits early and no output files appear

Fix:
- rerun from the project root
- check whether the input file exists
- confirm dependencies were installed with `pip install -r requirements.txt`

### Cache seems stale

Symptom:
- you want to force a fresh recomputation for the current scope

Fix:
- rerun with `--refresh`

Example:

```bash
python run_agent.py examples/sample_paper.docx --scope intro --refresh
```
