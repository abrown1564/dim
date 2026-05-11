#!/usr/bin/env python3
"""
Stage 3: Discourse Skeleton Merge

Merges all unit skeletons for a debate into one unified discourse skeleton.
Reads from the skeletons table, writes to the discourse_skeletons table.

Usage:
    python pipeline/merge_discourse.py <debate_id> [--db data/dim_corpus.db] [--model claude-opus-4-7]
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

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "long_transcript_merge_prompt.md"

SYSTEM_PROMPT = """You are a discourse skeleton synthesiser for the Discourse Integrity Map pipeline.

Merge the unit skeletons below into a single coherent discourse skeleton. Follow the rules precisely.

Return ONLY valid YAML — no preamble, no markdown fences, no commentary."""


def load_prompt() -> str:
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
        return None


def format_skeletons_for_merge(skeletons) -> str:
    blocks = []
    for i, s in enumerate(skeletons, 1):
        stasis = json.loads(s["stasis_points"] or "[]")
        facts = json.loads(s["facts_to_verify"] or "[]")
        block = f"--- Unit {i} ---\n"
        block += f"Summary: {s['section_summary'] or '(none)'}\n"
        if stasis:
            block += "Stasis points:\n"
            for sp in stasis:
                block += f"  - [{sp.get('stasis_type', '?')}] {sp.get('question_at_issue', '')}\n"
                for claim in sp.get("speaker_claims", []):
                    block += f"    • {claim.get('speaker', '?')}: {claim.get('claim', '')}\n"
        if facts:
            block += "Facts to verify:\n"
            for f in facts:
                block += f"  - {f}\n"
        blocks.append(block)
    return "\n".join(blocks)


def merge_discourse(debate_id: str, model: str, db_path: Path) -> bool:
    debate = db.get_debate(debate_id, db_path)
    if not debate:
        print(f"Debate not found: {debate_id}")
        return False

    title = debate["video_title"] or debate_id
    discourse_mode = debate["discourse_mode"] or "unknown"

    with db.connect(db_path) as con:
        skeletons = con.execute(
            """SELECT s.* FROM skeletons s
               JOIN units u ON s.unit_id = u.unit_id
               WHERE s.debate_id = ? AND s.usable_argument = 1
               ORDER BY u.unit_index""",
            (debate_id,),
        ).fetchall()

    if not skeletons:
        print(f"No usable skeletons found for debate {debate_id}. Run skeletonize_units.py first.")
        return False

    print(f"\n  Debate   : {title}")
    print(f"  Skeletons: {len(skeletons)}")
    print(f"  Merging...", end=" ", flush=True)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set.")
    client = anthropic.Anthropic(api_key=api_key)

    prompt_instructions = load_prompt()
    skeleton_summary = format_skeletons_for_merge(skeletons)

    user_content = f"""{prompt_instructions}

DEBATE METADATA:
- discourse_mode: {discourse_mode}
- title: {title}

UNIT SKELETONS:
---
{skeleton_summary}
---"""

    msg = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    parsed = parse_yaml_response(msg.content[0].text)
    if not parsed:
        print("parse failed")
        return False

    print("ok")

    src = parsed.get("source_summary", {}) or {}
    now = datetime.now(timezone.utc).isoformat()

    def _tri(val) -> str:
        """Normalise LLM tri-state values to 'yes' | 'no' | 'partial'."""
        if val is True or str(val).lower() in ("yes", "true", "1"):
            return "yes"
        if val is False or str(val).lower() in ("no", "false", "0"):
            return "no"
        if str(val).lower() == "partial":
            return "partial"
        return "no"  # n/a, null, unknown → treat as no

    with db.connect(db_path) as con:
        con.execute("DELETE FROM discourse_skeletons WHERE debate_id = ?", (debate_id,))
        con.execute(
            """INSERT INTO discourse_skeletons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                debate_id,
                src.get("discourse_mode", discourse_mode),
                src.get("overall_topic"),
                _tri(src.get("agreement_reached")),
                _tri(src.get("consensus_reached")),
                json.dumps(src.get("common_ground_identified", [])),
                json.dumps(parsed.get("participants", [])),
                json.dumps(parsed.get("major_stasis_points", [])),
                json.dumps(parsed.get("facts_to_verify", [])),
                json.dumps(parsed.get("assumptions_to_test", [])),
                json.dumps(parsed.get("terms_to_define", [])),
                parsed.get("meta_comment"),
                yaml.dump(parsed),
                now,
            ),
        )
        con.commit()

    print(f"  ✓  Discourse skeleton stored for debate {debate_id}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Stage 3: Merge unit skeletons into discourse skeleton")
    parser.add_argument("debate_id", help="Debate UUID from the debates table")
    parser.add_argument("--db",    type=Path, default=db.DB_PATH)
    parser.add_argument("--model", default="claude-opus-4-7")
    args = parser.parse_args()

    db.migrate(args.db)
    merge_discourse(args.debate_id, args.model, args.db)


if __name__ == "__main__":
    main()
