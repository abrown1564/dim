#!/usr/bin/env python3
"""
Stage 1: Argumentative Unit Detection

Segments a debate transcript into coherent argumentative units.
Reads from the debates table, writes to the units table.

Usage:
    python pipeline/detect_units.py <debate_id> [--db data/dim_corpus.db] [--model claude-opus-4-7]
    python pipeline/detect_units.py --list
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
    sys.exit("anthropic package not found. Run: pip install -r requirements.txt")

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

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "argumentative_unit_detection_prompt.md"

SYSTEM_PROMPT = """You are an argumentative unit detector for the Discourse Integrity Map pipeline.

Segment the transcript below into coherent argumentative units. Follow the rules in the instructions precisely.

Return ONLY valid YAML — no preamble, no markdown fences, no commentary."""


def load_detection_prompt() -> str:
    if not PROMPT_PATH.exists():
        sys.exit(f"Prompt not found at {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def parse_yaml_response(raw: str) -> dict | None:
    raw = raw.strip()
    raw = re.sub(r"^```(?:yaml)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as e:
        print(f"  Warning: YAML parse error: {e}", file=sys.stderr)
        print(f"  Raw (first 300): {raw[:300]}", file=sys.stderr)
        return None


def chunk_transcript(text: str, max_chars: int = 12000) -> list[tuple[str, int]]:
    """Split long transcripts into overlapping chunks.

    Returns list of (chunk_text, line_offset) where line_offset is the
    number of lines before this chunk in the full transcript, so that
    line numbers from the LLM can be converted to transcript-absolute.
    """
    if len(text) <= max_chars:
        return [(text, 0)]
    chunks = []
    step = max_chars - 1000  # 1000 char overlap
    for start in range(0, len(text), step):
        chunk = text[start:start + max_chars]
        line_offset = text[:start].count("\n")
        chunks.append((chunk, line_offset))
    return chunks


def detect_units(debate_id: str, model: str, db_path: Path) -> int:
    debate = db.get_debate(debate_id, db_path)
    if not debate:
        print(f"Debate not found: {debate_id}")
        return 0

    transcript = debate["transcript_text"]
    if not transcript:
        print(f"No transcript text for debate: {debate_id}")
        return 0

    title = debate["video_title"] or debate_id
    discourse_mode = debate["discourse_mode"] or "unknown"

    print(f"\n  Debate  : {title}")
    print(f"  Mode    : {discourse_mode}")
    print(f"  Length  : {len(transcript):,} chars")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set.")
    client = anthropic.Anthropic(api_key=api_key)

    prompt_instructions = load_detection_prompt()
    chunks = chunk_transcript(transcript)
    print(f"  Chunks  : {len(chunks)}")

    all_units = []
    unit_counter = 0

    for i, (chunk, line_offset) in enumerate(chunks, 1):
        print(f"  [{i}/{len(chunks)}] Detecting units...", end=" ", flush=True)

        user_content = f"""{prompt_instructions}

DISCOURSE MODE: {discourse_mode}

TRANSCRIPT:
---
{chunk}
---"""

        msg = client.messages.create(
            model=model,
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        parsed = parse_yaml_response(msg.content[0].text)
        if not parsed or "units" not in parsed:
            print("no units found")
            continue

        chunk_units = parsed["units"]
        # Adjust chunk-relative line numbers to transcript-absolute
        if line_offset:
            for u in chunk_units:
                if u.get("start_line") is not None:
                    u["start_line"] += line_offset
                if u.get("end_line") is not None:
                    u["end_line"] += line_offset
        print(f"{len(chunk_units)} units")
        all_units.extend(chunk_units)

    # Deduplicate by start_excerpt across chunks
    seen = set()
    deduped = []
    for u in all_units:
        key = u.get("start_excerpt", "")[:80]
        if key not in seen:
            seen.add(key)
            deduped.append(u)
        unit_counter = len(deduped)

    # Write to DB
    now = datetime.now(timezone.utc).isoformat()
    with db.connect(db_path) as con:
        # Clear any existing units for this debate before re-inserting
        con.execute("DELETE FROM units WHERE debate_id = ?", (debate_id,))

        for idx, u in enumerate(deduped):
            speakers = u.get("speakers", [])
            con.execute(
                """INSERT INTO units VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )""",
                (
                    str(uuid.uuid4()),
                    debate_id,
                    idx,
                    u.get("unit_type"),
                    u.get("main_issue"),
                    json.dumps(speakers),
                    u.get("start_excerpt"),
                    u.get("end_excerpt"),
                    u.get("start_line"),
                    u.get("end_line"),
                    1 if u.get("usable_for_skeletonisation", True) else 0,
                    u.get("reliability", "medium"),
                    u.get("reason_if_low_or_false"),
                    yaml.dump(u),
                    now,
                ),
            )
        con.commit()

    print(f"\n  ✓  {unit_counter} units stored for debate {debate_id}")
    return unit_counter


def main():
    parser = argparse.ArgumentParser(description="Stage 1: Detect argumentative units in a debate transcript")
    parser.add_argument("debate_id", nargs="?", help="Debate UUID from the debates table")
    parser.add_argument("--db",    type=Path, default=db.DB_PATH)
    parser.add_argument("--model", default="claude-opus-4-7")
    parser.add_argument("--list",  action="store_true", help="List available debates and exit")
    args = parser.parse_args()

    db.migrate(args.db)

    if args.list:
        debates = db.list_debates(args.db)
        print(f"\n{'ID':<38}  {'Mode':<12}  Title")
        print("─" * 90)
        for d in debates:
            print(f"{d['debate_id']}  {(d['discourse_mode'] or 'unknown'):<12}  {d['video_title'] or '(untitled)'}")
        return

    if not args.debate_id:
        parser.print_help()
        return

    detect_units(args.debate_id, args.model, args.db)


if __name__ == "__main__":
    main()
