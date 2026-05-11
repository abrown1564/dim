#!/usr/bin/env python3
"""
Stage 5: Discourse Profile Assembly

Counts technique detections per debate and assembles the discourse profile.
Reads from detections + discourse_skeletons, writes to the profiles table
and outputs a JSON profile file.

Usage:
    python pipeline/assemble_profile.py <debate_id> [--db data/dim_corpus.db] [--out data/profiles/]
"""

import argparse
import json
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import db


def assemble_profile(debate_id: str, db_path: Path, out_dir: Path) -> dict | None:
    debate = db.get_debate(debate_id, db_path)
    if not debate:
        print(f"Debate not found: {debate_id}")
        return None

    title = debate["video_title"] or debate_id

    with db.connect(db_path) as con:
        detections = con.execute(
            "SELECT * FROM detections WHERE debate_id = ?", (debate_id,)
        ).fetchall()

        skeletons = con.execute(
            "SELECT * FROM skeletons WHERE debate_id = ? AND usable_argument = 1",
            (debate_id,),
        ).fetchall()

        ds = con.execute(
            "SELECT * FROM discourse_skeletons WHERE debate_id = ?", (debate_id,)
        ).fetchone()

    # Count techniques, grouped by type
    technique_counts = defaultdict(lambda: {"count": 0, "polarity": None, "classifier_group": None, "examples": []})
    for d in detections:
        t = d["technique_type"] or "unknown"
        technique_counts[t]["count"] += 1
        technique_counts[t]["polarity"] = d["polarity"]
        technique_counts[t]["classifier_group"] = d["classifier_group"]
        if len(technique_counts[t]["examples"]) < 2:
            technique_counts[t]["examples"].append({
                "evidence":   d["evidence"],
                "confidence": d["confidence"],
                "unit_id":    d["unit_id"],
            })

    techniques = [
        {
            "type":             t,
            "count":            v["count"],
            "polarity":         v["polarity"],
            "classifier_group": v["classifier_group"],
            "examples":         v["examples"],
        }
        for t, v in sorted(technique_counts.items(), key=lambda x: -x[1]["count"])
    ]

    negative = [d for d in detections if d["polarity"] == "negative"]
    positive = [d for d in detections if d["polarity"] == "positive"]

    profile = {
        "debate_id":      debate_id,
        "title":          title,
        "discourse_mode": debate["discourse_mode"],
        "speaker_count":  debate["speaker_count"],
        "published_date": debate["published_date"],
        "source_url":     debate["source_url"],
        "unit_count":     len(skeletons),
        "dialectical_conduct": {
            "total_detections": len(detections),
            "negative_count":   len(negative),
            "positive_count":   len(positive),
            "techniques":       techniques,
        },
        "discourse_skeleton": {
            "overall_topic":       ds["overall_topic"] if ds else None,
            "agreement_reached":   ds["agreement_reached"] if ds else None,
            "consensus_reached":   ds["consensus_reached"] if ds else None,
            "major_stasis_points": json.loads(ds["major_stasis_points"]) if ds else [],
            "facts_to_verify":     json.loads(ds["facts_to_verify"]) if ds else [],
            "meta_comment":        ds["meta_comment"] if ds else None,
        },
        "assembled_at": datetime.now(timezone.utc).isoformat(),
    }

    # Write profile JSON
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in (title or debate_id))[:60]
    out_path = out_dir / f"{safe_title.strip()}.json"
    out_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")

    # Write to DB (simplified — no scoring columns, store full profile JSON)
    now = datetime.now(timezone.utc).isoformat()
    with db.connect(db_path) as con:
        con.execute("DELETE FROM profiles WHERE debate_id = ?", (debate_id,))
        con.execute(
            "INSERT INTO profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                debate_id,
                len(skeletons),
                None, None, None, None,  # scoring columns reserved for later
                json.dumps(profile),
                now,
            ),
        )
        con.commit()

    print(f"\n  Debate   : {title}")
    print(f"  Units    : {len(skeletons)}")
    print(f"  Negative : {len(negative)} detections")
    print(f"  Positive : {len(positive)} detections")
    print(f"  Techniques detected: {len(techniques)}")
    print(f"  ✓  Profile → {out_path}")

    return profile


def main():
    parser = argparse.ArgumentParser(description="Stage 5: Assemble discourse profile")
    parser.add_argument("debate_id", help="Debate UUID from the debates table")
    parser.add_argument("--db",  type=Path, default=db.DB_PATH)
    parser.add_argument("--out", type=Path, default=Path("data/profiles"))
    args = parser.parse_args()

    db.migrate(args.db)
    assemble_profile(args.debate_id, args.db, args.out)


if __name__ == "__main__":
    main()
