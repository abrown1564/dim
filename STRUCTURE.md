# DIM Repository Structure

**Discourse Integrity Map — MVP**
A pipeline for analysing rhetorical and argumentative quality in public discourse, applied to a wealth-tax YouTube corpus.

---

## Top-Level Files

| File | Role |
|---|---|
| `README.md` | Project overview, corpus stats, key files, DB note, how to run. |
| `STRUCTURE.md` | This file. Full repo structure and architectural decisions. |
| `report_draft.md` | Reader-facing project report: aims, what was built, limitations, further work. |
| `provenance_schema.md` | Schema for taxonomy provenance fields (established / adapted / coined). |
| `agent_debate_summary.md` | Summary output from the multi-agent debate architecture experiment. |
| `.gitignore` | Standard ignores. |

---

## `pipeline/` — Core Pipeline Scripts

### Ingestion

| Script | Role |
|---|---|
| `ingest_youtube.py` | Downloads a YouTube video, runs pyannote.audio diarisation + Whisper transcription, and saves a structured `.txt` file with a standard metadata header. Entry point for adding new content to the corpus. Supports `--discourse-mode`, `--diarise`, `--no-prompt` flags. |
| `ingest_corpus.py` | Reads transcript files from a directory, parses their metadata headers, and ingests them into the SQLite corpus database (`dim_corpus.db`). Assigns each debate a UUID. Idempotent — skips already-ingested files. |

### Analysis Pipeline (run in order)

The analysis pipeline processes one debate at a time through 5 stages. Use `run_pipeline.py` to chain them, or run each script individually.

```
transcript (in DB)
    │
    ▼
[1] detect_units.py        Segments transcript into argumentative units
    │                      Prompt: prompts/argumentative_unit_detection_prompt.md
    ▼
DB: units table
    │
    ▼
[2] skeletonize_units.py   Extracts minimal argumentative skeleton per unit
    │                      Prompt: prompts/unit_skeletonization_prompt.md
    ▼
DB: skeletons table
    │
    ▼
[3] merge_discourse.py     Merges all unit skeletons into one discourse skeleton
    │                      Prompt: prompts/long_transcript_merge_prompt.md
    ▼
DB: discourse_skeletons table
    │
    ▼
[4] classify_units.py      Runs 7 rhetoric/fallacy detector groups on each unit
    │                      Grounded on: skeleton + verbatim excerpt
    │                      Counts technique detections per unit
    ▼
DB: detections table
    │
    ▼
[5] assemble_profile.py    Aggregates detection counts into discourse profile
    │                      Outputs JSON to data/profiles/
    ▼
DB: profiles table  +  data/profiles/<title>.json
```

| Script | Role |
|---|---|
| `detect_units.py` | **Stage 1.** Calls Claude with the unit detection prompt to segment a full transcript into coherent argumentative units. Handles long transcripts by chunking with overlap. Writes unit boundaries, type, reliability, and excerpts to the `units` table. |
| `skeletonize_units.py` | **Stage 2.** For each usable unit, calls Claude with the skeletonization prompt to extract stasis points, speaker claims, warrants, facts to verify, and a source-anchored verbatim excerpt. Writes to the `skeletons` table. |
| `merge_discourse.py` | **Stage 3.** Merges all unit-level skeletons for a debate into one unified discourse skeleton: major recurring stasis points, participant roles, agreement/consensus status, facts to verify. Writes to the `discourse_skeletons` table. |
| `classify_units.py` | **Stage 4.** Runs 7 classifier groups (formal logic violations, source attacks, evidence quality, semantic manipulation, psychological rhetoric, networked/platform, counter-techniques) on each unit's verbatim excerpt + skeleton summary. Respects discourse mode gating (monologic suppresses interaction-dependent techniques). Writes to the `detections` table. |
| `assemble_profile.py` | **Stage 5.** Aggregates detection counts by technique type, assembles the discourse profile (counts only — no scoring for MVP), and writes a JSON profile file to `data/profiles/`. Also writes to the `profiles` table. |
| `run_pipeline.py` | **Master runner.** Chains all 5 stages for a single debate. Supports `--from-stage N` to resume from a specific stage. Use `--list` to see available debates. |

### Site Builder Scripts

| Script | Role |
|---|---|
| `build_corpus_cards.py` | Generates `site/data/corpus_cards.json` for the debate profile cards page. |
| `build_corpus_json.py` | Generates `site/data/corpus.json` for the map visualisation. |
| `build_heatmap.py` | Generates `site/data/heatmap.json` for the technique × stance heatmap. Normalises by unit count per stance for comparability. |
| `build_sunburst.py` | Generates sunburst chart data and patches constants directly into `site/sunburst.html`. |
| `build_taxonomy_html.py` | Generates `site/taxonomy.html` from `pipeline/taxonomy.json`. |

### Position Aggregation

| Script | Role |
|---|---|
| `merge_positions.py` | Merges the two-prompt LLM aggregation outputs into `site/data/claim_positions.json`. Hardcodes the first-prompt canonical positions (wealth-tax corpus specific); joins with `claim_provenance.json` for source indices and example quotes; builds debate objects from `claims_index.json`. See note at top of file. |

### Supporting Utilities

| Script | Role |
|---|---|
| `db.py` | Shared database layer. Defines the full SQLite schema, migration function, and connection helpers used by all pipeline scripts. |
| `input_utils.py` | Shared helper: loads text from a URL, file path, or stdin. |
| `output_utils.py` | Shared helper: appends/overwrites JSON output files. |

### Data Files

| File | Role |
|---|---|
| `taxonomy.json` | The DIM fallacy/technique taxonomy. Source of truth for all classifier groups and technique definitions. |
| `debate_terminology.json` | Debate-specific terminology reference. |
| `sources.json` | Source metadata registry with platform reach methodology notes. |
| `requirements.txt` | Python dependencies for the pipeline. |

### Experimental (`pipeline/experimental/`)

| Script | Role |
|---|---|
| `run_agent_debate.py` | Runs a multi-agent AI debate over the canonical wealth-tax positions. Agents are assigned personas from `site/data/agent_personas.json` and vote/respond over 3 rounds. Output is a timestamped event log used by `site/debate.html`. |
| `generate_demo_debate.py` | Generates a synthetic debate event log for `site/debate.html` without making API calls. Used for demos and development. |

---

## `prompts/` — LLM Prompt Templates

| File | Role |
|---|---|
| `argumentative_unit_detection_prompt.md` | **Stage 1 prompt.** Instructions for segmenting a transcript into argumentative units by coherence. Defines unit types, reliability flags, and YAML output schema. |
| `unit_skeletonization_prompt.md` | **Stage 2 prompt.** Instructions for extracting the minimal faithful argumentative structure of one unit. Outputs stasis points, claims, warrants, facts to verify, and a verbatim excerpt. |
| `long_transcript_merge_prompt.md` | **Stage 3 prompt.** Instructions for merging local unit skeletons into one discourse skeleton. Rules: do not invent agreement, preserve disagreement structure, merge only substantively identical claims. |
| `aggregation_prompt.txt` | First aggregation prompt: condenses 456 individual claims into canonical argument positions with stance, stasis, and context metadata. |
| `aggregation_provenance_prompt.txt` | Second aggregation prompt: maps each canonical position back to its source claim indices and example quotes. |
| `manual_skeletonisation_template.md` | Human-fillable reference template for manual skeletonisation. The normative form that the automated prompts are designed to replicate. |

---

## `data/` — Database and Profiles

| File/Folder | Role |
|---|---|
| `dim_corpus.db` | SQLite database. Tables: `debates`, `units`, `skeletons`, `discourse_skeletons`, `detections`, `profiles`, `claims`. Primary key for all debate-level data is a UUID (`debate_id`). Committed to repo — regenerating requires Claude API access and credits. |
| `profiles/` | JSON discourse profiles — one per processed debate, produced by Stage 5. 17 files corresponding to the 17 processed debates. |

---

## `site/` — Static Site

No backend, no database, no framework. Hosted on GitHub Pages. All data files are pre-built JSON read directly by the browser.

### Pages

| File | Role |
|---|---|
| `positions.html` | Canonical argument positions map — filterable by side, stasis, and context. |
| `corpus.html` | Debate profile cards — per-debate breakdown with discourse mode and top techniques. |
| `heatmap.html` | Technique × stance heatmap — normalised detection rates across pro/anti/neutral. |
| `map.html` | Map visualisation of the corpus. |
| `sunburst.html` | Sunburst chart of technique distribution. |
| `debate.html` | Multi-agent debate replay visualisation. |
| `taxonomy.html` | Rendered taxonomy reference browser. |
| `traditions.html` | Rhetorical traditions reference page. |

### `site/data/` — Pre-built Data Files

| File | Role |
|---|---|
| `claim_positions.json` | 37 canonical positions (32 pro/anti + 5 shared) with provenance. Primary data file for `positions.html`. |
| `claims_index.json` | All 456 extracted claims with debate, speaker, stance, stasis, and quote. |
| `claim_provenance.json` | Raw second-prompt LLM output: source indices and example quotes per position. Source file for `merge_positions.py`. |
| `corpus.json` | Debate metadata for map visualisation. |
| `corpus_cards.json` | Per-debate summary cards for `corpus.html`. |
| `heatmap.json` | Normalised technique detection rates by stance. |
| `sunburst.json` | Technique distribution data for sunburst chart. |
| `technique_info.json` | Full definitions and notes for every taxonomy technique. |
| `agent_debate_log.json` | Event log from the multi-agent debate run. Used by `debate.html`. |
| `agent_personas.json` | Agent persona definitions for the multi-agent debate. |

---

## Database Schema Summary

```
debates               — one row per ingested source (UUID primary key)
units                 — argumentative units per debate (Stage 1 output)
skeletons             — unit-level argumentative skeletons (Stage 2 output)
discourse_skeletons   — merged debate-level skeleton (Stage 3 output)
detections            — technique detections per unit (Stage 4 output)
profiles              — assembled discourse profiles (Stage 5 output)
claims                — extracted claims per debate
```

All tables link to `debates` via `debate_id`. All analysis tables link to `units` via `unit_id`.

---

## Key Architectural Decisions

- **No scoring for MVP.** Profile records technique counts only. Scoring methodology (flat polarity, normalised by unit count) is designed but deferred until there is enough data to justify weights.
- **Unit-based classification.** The classifier runs once per argumentative unit (not once per full transcript), so detections are anchored to specific argumentative moments.
- **Skeleton before rhetoric.** The argumentative structure is extracted first (Stages 1–3) before rhetoric is detected (Stage 4). Rhetorical labels attach to identified claims, not raw text.
- **Grounded scoring core / flag-only halo.** Only techniques cleanly anchored to Aristotelian or pragma-dialectical frameworks contribute to the grounded record. Networked/platform and coined-term techniques are detected and stored but flagged separately.
- **Discourse mode gating.** Interaction-dependent techniques (foreclosing interrogation, many questions, turn-taking failures) are suppressed for monologic content.
- **Abstention is valid.** Classifiers may return no detections. No forced classification.
- **Static site, no backend.** All site data is pre-built JSON committed to the repo and read directly by the browser. No server required.
- **DB committed to repo.** `dim_corpus.db` is in version control because regenerating it requires Claude API credits. The DB is the canonical pipeline state; the site JSON files are derived from it.
