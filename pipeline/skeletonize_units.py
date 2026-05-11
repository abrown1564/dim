#!/usr/bin/env python3
"""
Stage 2: Unit Skeletonization

Extracts the minimal faithful argumentative skeleton from each unit.
Reads from the units table, writes to the skeletons table.

Usage:
    python pipeline/skeletonize_units.py <debate_id> [--db data/dim_corpus.db] [--model claude-opus-4-7]
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit("anthropic package not found.")

try:
    import yaml
except ImportError:
    sys.exit("PyYAML not found. Run: pip install pyyaml")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
import db

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "unit_skeletonization_prompt.md"

SYSTEM_PROMPT = """You are an argumentative skeleton extractor for the Discourse Integrity Map pipeline.

Extract the minimal faithful argumentative structure of the unit below. Follow the rules precisely.

Return ONLY valid YAML — no preamble, no markdown fences, no commentary."""


def load_prompt() -> str:
    if not PROMPT_PATH.exists():
        sys.exit(f"Prompt not found at {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def parse_yaml_response(raw: str) -> dict | None:
    raw = raw.strip()
    raw = re.sub(r"^```(?:yaml)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    # Collapse mid-document YAML separators the LLM occasionally emits
    raw = re.sub(r"\n---+\n", "\n", raw)
    # Strip inline parenthetical annotations after list-item strings, e.g.:
    #   - "term" (clarification here)  →  - "term"
    raw = re.sub(r'(^\s*-\s+"[^"]*")\s+\([^)]*\)', r"\1", raw, flags=re.MULTILINE)
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as e:
        print(f"    Warning: YAML parse error: {e}", file=sys.stderr)
        return None


def get_unit_text(debate_transcript: str, unit: sqlite3.Row) -> str:
    """Extract the verbatim unit text from the full transcript using line numbers or excerpts."""
    start_line = unit["start_line"]
    end_line = unit["end_line"]

    if start_line is not None and end_line is not None:
        lines = debate_transcript.splitlines()
        return "\n".join(lines[max(0, start_line - 1):end_line])

    # Fall back to excerpt-based extraction
    start_exc = unit["start_excerpt"] or ""
    end_exc = unit["end_excerpt"] or ""
    if start_exc and start_exc in debate_transcript:
        start_pos = debate_transcript.index(start_exc)
        if end_exc and end_exc in debate_transcript:
            end_pos = debate_transcript.index(end_exc) + len(end_exc)
            return debate_transcript[start_pos:end_pos]
        return debate_transcript[start_pos:start_pos + 8000]

    return unit["start_excerpt"] or ""


def skeletonize_debate(debate_id: str, model: str, db_path: Path) -> int:
    debate = db.get_debate(debate_id, db_path)
    if not debate:
        print(f"Debate not found: {debate_id}")
        return 0

    transcript = debate["transcript_text"] or ""
    title = debate["video_title"] or debate_id

    with db.connect(db_path) as con:
        units = con.execute(
            "SELECT * FROM units WHERE debate_id = ? AND usable = 1 ORDER BY unit_index",
            (debate_id,),
        ).fetchall()

    if not units:
        print(f"No usable units found for debate {debate_id}. Run detect_units.py first.")
        return 0

    print(f"\n  Debate  : {title}")
    print(f"  Units   : {len(units)} usable")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set.")
    client = anthropic.Anthropic(api_key=api_key)

    prompt_instructions = load_prompt()
    now = datetime.now(timezone.utc).isoformat()
    count = 0

    with db.connect(db_path) as con:
        con.execute("DELETE FROM skeletons WHERE debate_id = ?", (debate_id,))
        con.execute("DELETE FROM claims WHERE debate_id = ?", (debate_id,))
        con.commit()

    for unit in units:
        unit_idx = unit["unit_index"]
        unit_type = unit["unit_type"] or "unknown"
        print(f"  [{unit_idx + 1}/{len(units)}] {unit_type} — {(unit['main_issue'] or '')[:60]}...", end=" ", flush=True)

        unit_text = get_unit_text(transcript, unit)
        if not unit_text.strip():
            print("no text, skipping")
            continue

        user_content = f"""{prompt_instructions}

UNIT METADATA:
- unit_id: {unit['unit_id']}
- unit_type: {unit_type}
- main_issue: {unit['main_issue'] or 'unknown'}
- speakers: {unit['speakers'] or '[]'}
- start_line: {unit['start_line']}
- end_line: {unit['end_line']}

UNIT TEXT:
---
{unit_text}
---"""

        msg = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        parsed = parse_yaml_response(msg.content[0].text)
        if not parsed:
            print("parse failed")
            continue

        anchor = parsed.get("source_anchor", {}) or {}
        stasis = parsed.get("local_stasis_points", [])
        verbatim = anchor.get("verbatim_excerpt") or unit_text
        skeleton_id = str(uuid.uuid4())

        with db.connect(db_path) as con:
            con.execute(
                """INSERT INTO skeletons
                   (skeleton_id, unit_id, debate_id, usable_argument, section_summary,
                    verbatim_excerpt, stasis_points, facts_to_verify, assumptions_to_test,
                    terms_to_define, policy_stance, raw_yaml, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    skeleton_id,
                    unit["unit_id"],
                    debate_id,
                    1 if parsed.get("usable_argument", True) else 0,
                    parsed.get("section_summary"),
                    verbatim,
                    json.dumps(stasis),
                    json.dumps(parsed.get("facts_to_verify", [])),
                    json.dumps(parsed.get("assumptions_to_test", [])),
                    json.dumps(parsed.get("terms_to_define", [])),
                    parsed.get("policy_stance"),
                    yaml.dump(parsed),
                    now,
                ),
            )

            # Unpack individual claims into the claims table
            for sp in stasis:
                stasis_type = sp.get("stasis_type")
                question = sp.get("question_at_issue")
                warrants = {w.get("speaker"): w.get("warrant") for w in sp.get("warrants", []) if isinstance(w, dict)}
                for claim_obj in sp.get("speaker_claims", []):
                    if not isinstance(claim_obj, dict):
                        continue
                    speaker = claim_obj.get("speaker")
                    con.execute(
                        """INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            str(uuid.uuid4()),
                            debate_id,
                            unit["unit_id"],
                            skeleton_id,
                            speaker,
                            claim_obj.get("claim"),
                            claim_obj.get("stance"),
                            stasis_type,
                            question,
                            warrants.get(speaker),
                            verbatim,
                            now,
                        ),
                    )

            con.commit()

        print("ok")
        count += 1

    print(f"\n  ✓  {count} skeletons stored for debate {debate_id}")
    return count


def main():
    parser = argparse.ArgumentParser(description="Stage 2: Skeletonize argumentative units")
    parser.add_argument("debate_id", help="Debate UUID from the debates table")
    parser.add_argument("--db",    type=Path, default=db.DB_PATH)
    parser.add_argument("--model", default="claude-opus-4-7")
    args = parser.parse_args()

    db.migrate(args.db)
    skeletonize_debate(args.debate_id, args.model, args.db)


if __name__ == "__main__":
    main()
