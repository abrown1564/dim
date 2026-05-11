# Discourse Integrity Map

A computational pipeline for mapping the quality and structure of public argument. It ingests debate transcripts, extracts individual speaker claims, classifies them against a discourse-quality taxonomy, and aggregates them into canonical argument positions — surfacing where sides diverge, where latent agreement already exists, and what kind of disagreement underlies a debate.

The current MVP applies this to the UK/US public debate over wealth taxation. It identifies five shared ground positions held by both sides — claims that get lost in the argument about the instrument but which could form the basis of more productive deliberation.

The framework assesses **how** arguments are made, not whether conclusions are correct — grounded in the Aristotelian dialectic/eristic distinction between arguing to find truth and arguing to win.

---

## Corpus

- 31 debates identified; 17 processed through the full pipeline (API credits exhausted before completion)
- 456 claims extracted; 37 canonical positions aggregated (32 pro/anti + 5 shared ground)
- UK and US contexts; primarily YouTube panel debates, interviews, and monologic commentary

---

## What It Does

```
YouTube URL
    │
    ▼
ingest_youtube.py      Download transcript + diarise speakers
    │
    ▼
ingest_corpus.py       Load transcript into SQLite database
    │
    ▼
run_pipeline.py        Run 5 analysis stages per debate:
    │                    1. detect_units       — segment into argumentative units
    │                    2. skeletonize_units  — extract claims, warrants, stasis points
    │                    3. merge_discourse    — merge into unified discourse skeleton
    │                    4. classify_units     — detect rhetorical/fallacious techniques
    │                    5. assemble_profile   — aggregate into discourse profile
    ▼
dim_corpus.db          Canonical pipeline database
    │
    ▼
build_*.py scripts     Generate pre-built JSON for the static site
    │
    ▼
site/                  Static site served via GitHub Pages
```

---

## Quickstart

### Just browse the data

Open `site/positions.html` in a browser, or visit the GitHub Pages URL. No setup required — all data is pre-built.

### Explore the database

```bash
sqlite3 data/dim_corpus.db
.tables
SELECT title FROM debates;
```

### Extend the corpus with a new debate

**Requirements:** Python 3.10+, an Anthropic API key, `ffmpeg` (for Whisper fallback).

```bash
pip install -r pipeline/requirements.txt
export ANTHROPIC_API_KEY=your_key_here
```

**1. Ingest a YouTube video:**
```bash
python pipeline/ingest_youtube.py <youtube_url> --discourse-mode dialogic
```
This downloads the transcript (captions or Whisper fallback), diarises speakers, and saves a structured `.txt` file.

**2. Load the transcript into the database:**
```bash
python pipeline/ingest_corpus.py <transcript_directory>
```

**3. Run the analysis pipeline:**
```bash
python pipeline/run_pipeline.py --list          # see available debates
python pipeline/run_pipeline.py --debate <id>   # run all 5 stages
python pipeline/run_pipeline.py --debate <id> --from-stage 3  # resume from a stage
```
Note: each debate makes multiple Claude API calls across the 5 stages. Budget accordingly.

**4. Rebuild the site data:**
```bash
python pipeline/build_corpus_cards.py
python pipeline/build_corpus_json.py
python pipeline/build_heatmap.py
python pipeline/build_sunburst.py
```

---

## Database Note

`data/dim_corpus.db` is committed to this repo. Regenerating it requires Claude API access and credits — re-running the pipeline is not a free operation. The DB is included so the project is usable and auditable without re-incurring those costs.

Tables: `debates` (31), `claims` (462), `detections` (390), `profiles` (17), `units`, `skeletons`, `discourse_skeletons`.

---

## Repo Structure

```
pipeline/              Pipeline scripts and data files
pipeline/experimental/ Experimental scripts (agent debate, demo generation)
prompts/               LLM prompt templates for each pipeline stage
data/                  SQLite database and per-debate profile JSONs
site/                  Static site HTML pages
site/data/             Pre-built JSON data files read by the site
site/report.html       Project report (background, methodology, findings, limitations, further work)
provenance_schema.md   Schema for taxonomy provenance fields
STRUCTURE.md           Full file-by-file reference and architectural decisions
```

For a full breakdown of every file and key architectural decisions, see [STRUCTURE.md](STRUCTURE.md).

---

## Site Pages

| Page | What it shows |
|------|---------------|
| `report.html` | Project report: background, methodology, findings, limitations, further work |
| `positions.html` (The Agora) | 37 canonical argument positions including 5 shared ground, filterable by side, stasis, and context |
| `corpus.html` | Per-debate profile cards with discourse mode and top techniques |
| `heatmap.html` | Technique × stance heatmap (normalised detection rates) |
| `debate.html` | Multi-agent debate replay built from corpus-derived personas |
| `taxonomy.html` | Full taxonomy browser - 191 entries across 9 categories |
| `traditions.html` | Rhetorical traditions reference (Aristotle, pragma-dialectics, biblical speech ethics, modern argumentation theory) |
| `map.html` | Corpus map visualisation |
| `dissertation.html` | The MSc dissertation that preceded and motivated the project |
