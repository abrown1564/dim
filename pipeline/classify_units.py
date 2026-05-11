#!/usr/bin/env python3
"""
Stage 4: Per-Unit Rhetoric Classification

Runs the DIM taxonomy classifier on each skeleton unit.
Reads from skeletons + units tables, writes to the detections table.

Usage:
    python pipeline/classify_units.py <debate_id> [--db data/dim_corpus.db] [--model claude-opus-4-7]
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit("anthropic package not found.")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
import db

PIPELINE_DIR = Path(__file__).parent
TAXONOMY_PATH = PIPELINE_DIR / "taxonomy.json"

POSITIVE_GROUPS = {"counter_techniques"}


# ── Classifier groups (same as classify.py) ───────────────────────────────────

CLASSIFIER_GROUPS = [
    {
        "id":          "formal_structure",
        "description": "formal logical structure violations",
        "networked":   False,
    },
    {
        "id":          "source_attacks",
        "description": "attacks on speaker credibility or source rather than argument substance",
        "networked":   False,
    },
    {
        "id":          "evidence_quality",
        "description": "failures in how evidence is selected, presented, or inferred from",
        "networked":   False,
    },
    {
        "id":          "semantic_manipulation",
        "description": "deceptive or evasive use of language, definitions, and framing",
        "networked":   False,
    },
    {
        "id":          "psychological_rhetoric",
        "description": "psychological pressure, emotional manipulation, and rhetorical performance substituting for argument",
        "networked":   False,
    },
    {
        "id":          "networked_platform",
        "description": "platform-native distortions and synthetic media signals",
        "networked":   True,
    },
    {
        "id":          "counter_techniques",
        "description": "positive good-faith argumentative moves that increase discourse quality",
        "networked":   False,
    },
]

MODE_GATE = {
    "monologic": {
        "suppress_contains": [
            "foreclosing_interrogation", "many_questions", "turn_taking",
            "loaded_question",
        ]
    }
}

DETECTION_SYSTEM = """You are a specialist classifier for the Discourse Integrity Map pipeline.

Identify instances of the specific argument patterns listed below in the text.

TAXONOMY ({group_description}):
{entries}

RULES:
1. Only flag instances with confidence ≥ 0.6
2. Every detection must include a specific verbatim quote from the text as evidence
3. Confidence reflects how clearly the text exemplifies this specific pattern
4. Incomplete argument ≠ fallacious. Absence-based labels (failure_to_steelman, cherry_picking, straw_man) require a materially strong omitted counterposition — not just ordinary incompleteness
5. If discourse_mode is monologic, suppress interaction-dependent techniques (foreclosing_interrogation, many_questions, turn_taking failures, loaded_question requiring live exchange)
6. Return [] if nothing meets the threshold
{extra_rules}

Return ONLY a JSON array — no preamble, no markdown fences:
[
  {{
    "type": "<id from taxonomy>",
    "confidence": <float 0.0–1.0>,
    "evidence": "<verbatim quote>"
  }}
]"""

COUNTER_SYSTEM = """You are a dialectical quality assessor for the Discourse Integrity Map pipeline.

Identify positive good-faith argumentative moves from the list below in the provided text.

COUNTER-TECHNIQUES:
{entries}

RULES:
1. Only flag instances with confidence ≥ 0.6
2. Every detection must include a specific verbatim quote as evidence
3. Return [] if nothing meets the threshold

Return ONLY a JSON array — no preamble, no markdown fences:
[
  {{
    "type": "<id from taxonomy>",
    "confidence": <float 0.0–1.0>,
    "evidence": "<verbatim quote>"
  }}
]"""

DETECTION_USER = """Classify the following argumentative unit.

UNIT SKELETON SUMMARY:
{skeleton_summary}

VERBATIM TEXT:
---
{verbatim}
---

DISCOURSE MODE: {discourse_mode}

Return only the JSON array."""

NETWORKED_NOTE = "\n7. For platform/networked mechanics: flag only if a clear textual signal is present. Full confirmation requires corpus-level analysis beyond a single unit."


def load_taxonomy() -> list[dict]:
    if not TAXONOMY_PATH.exists():
        sys.exit(f"Taxonomy not found at {TAXONOMY_PATH}")
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        return json.load(f)


def group_taxonomy(taxonomy: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for entry in taxonomy:
        g = entry.get("classifier_group")
        if g:
            groups.setdefault(g, []).append(entry)
    return groups


def era_lookup(taxonomy: list[dict]) -> dict[str, str]:
    return {e["id"]: e.get("era", "classical") for e in taxonomy if "id" in e}


def format_entries(entries: list[dict]) -> str:
    blocks = []
    for e in entries:
        aliases = ", ".join(e.get("aliases", []))
        provenance = e.get("provenance", "established")
        tag = " [coined]" if provenance == "coined" else ""
        lines = [f"### {e['name']} [{e['id']}]{tag}"]
        if aliases:
            lines.append(f"Also known as: {aliases}")
        lines.append(f"Definition: {e['definition']}")
        if e.get("distinguishing_features"):
            lines.append(f"Key marker: {e['distinguishing_features']}")
        if e.get("distinguishes_from"):
            contrasts = ", ".join(e["distinguishes_from"])
            lines.append(f"Do not confuse with: {contrasts}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def parse_json(raw: str) -> list:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []


def skeleton_summary(skeleton) -> str:
    summary = skeleton["section_summary"] or ""
    stasis = json.loads(skeleton["stasis_points"] or "[]")
    lines = [f"Summary: {summary}"]
    for sp in stasis:
        lines.append(f"Stasis [{sp.get('stasis_type', '?')}]: {sp.get('question_at_issue', '')}")
        for c in sp.get("speaker_claims", []):
            lines.append(f"  {c.get('speaker', '?')}: {c.get('claim', '')}")
    return "\n".join(lines)


def classify_unit(
    skeleton,
    unit,
    discourse_mode: str,
    grouped_taxonomy: dict,
    client,
    model: str,
    era_map: dict | None = None,
) -> list[dict]:
    verbatim = skeleton["verbatim_excerpt"] or ""
    if not verbatim.strip():
        return []

    skel_summary = skeleton_summary(skeleton)
    all_detections = []

    for group in CLASSIFIER_GROUPS:
        entries = grouped_taxonomy.get(group["id"], [])
        if not entries:
            continue

        formatted = format_entries(entries)
        is_counter = group["id"] == "counter_techniques"
        extra = NETWORKED_NOTE if group.get("networked") else ""

        if is_counter:
            system = COUNTER_SYSTEM.format(entries=formatted)
        else:
            system = DETECTION_SYSTEM.format(
                group_description=group["description"],
                entries=formatted,
                extra_rules=extra,
            )

        user = DETECTION_USER.format(
            skeleton_summary=skel_summary,
            verbatim=verbatim,
            discourse_mode=discourse_mode,
        )

        msg = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        detections = parse_json(msg.content[0].text)

        # Apply mode gating
        gate = MODE_GATE.get(discourse_mode, {})
        suppress = gate.get("suppress_contains", [])
        detections = [
            d for d in detections
            if not any(s in d.get("type", "") for s in suppress)
        ]

        for d in detections:
            if isinstance(d, dict):
                d["classifier_group"] = group["id"]
                d["polarity"] = "positive" if is_counter else "negative"
                d["weighted_score"] = round(
                    d.get("confidence", 0) * (0.1 if is_counter else -0.1), 4
                )
                if era_map is not None:
                    d["era"] = era_map.get(d.get("type", ""), d.get("era"))

        all_detections.extend([d for d in detections if isinstance(d, dict)])

    return all_detections


def classify_debate(debate_id: str, model: str, db_path: Path) -> int:
    debate = db.get_debate(debate_id, db_path)
    if not debate:
        print(f"Debate not found: {debate_id}")
        return False

    title = debate["video_title"] or debate_id
    discourse_mode = debate["discourse_mode"] or "unknown"

    with db.connect(db_path) as con:
        rows = con.execute(
            """SELECT s.*, u.unit_index, u.unit_type, u.main_issue
               FROM skeletons s
               JOIN units u ON s.unit_id = u.unit_id
               WHERE s.debate_id = ? AND s.usable_argument = 1
               ORDER BY u.unit_index""",
            (debate_id,),
        ).fetchall()

    if not rows:
        print(f"No usable skeletons found. Run skeletonize_units.py first.")
        return 0

    print(f"\n  Debate  : {title}")
    print(f"  Mode    : {discourse_mode}")
    print(f"  Units   : {len(rows)}")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set.")
    client = anthropic.Anthropic(api_key=api_key)

    taxonomy = load_taxonomy()
    grouped = group_taxonomy(taxonomy)
    eras = era_lookup(taxonomy)
    now = datetime.now(timezone.utc).isoformat()
    total_detections = 0

    with db.connect(db_path) as con:
        con.execute("DELETE FROM detections WHERE debate_id = ?", (debate_id,))
        con.commit()

    for row in rows:
        unit_label = f"u{row['unit_index'] + 1} [{row['unit_type'] or '?'}]"
        print(f"  {unit_label:<30} classifying...", end=" ", flush=True)

        detections = classify_unit(row, row, discourse_mode, grouped, client, model, era_map=eras)

        neg = sum(1 for d in detections if d["polarity"] == "negative")
        pos = sum(1 for d in detections if d["polarity"] == "positive")
        print(f"−{neg} +{pos}")

        with db.connect(db_path) as con:
            for d in detections:
                con.execute(
                    """INSERT INTO detections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        debate_id,
                        row["unit_id"],
                        row["skeleton_id"],
                        d.get("type"),
                        d.get("classifier_group"),
                        d.get("confidence"),
                        d.get("evidence"),
                        d.get("era"),
                        d.get("polarity"),
                        d.get("weighted_score"),
                        now,
                    ),
                )
            con.commit()

        total_detections += len(detections)

    print(f"\n  ✓  {total_detections} detections stored for debate {debate_id}")
    return total_detections


def main():
    parser = argparse.ArgumentParser(description="Stage 4: Classify rhetoric per argumentative unit")
    parser.add_argument("debate_id", help="Debate UUID from the debates table")
    parser.add_argument("--db",    type=Path, default=db.DB_PATH)
    parser.add_argument("--model", default="claude-opus-4-7")
    args = parser.parse_args()

    db.migrate(args.db)
    classify_debate(args.debate_id, args.model, args.db)


if __name__ == "__main__":
    main()
