#!/usr/bin/env python3
"""
build_corpus_cards.py

Generates site/data/corpus_cards.json for the debate profile cards page.

Each card contains everything needed to render a debate summary:
title, stance, discourse mode, top techniques, detection counts, and
whether any agreement was reached in the discourse skeleton.

Usage:
    python3 pipeline/build_corpus_cards.py
    python3 pipeline/build_corpus_cards.py --db data/dim_corpus.db
"""

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

DB_PATH  = Path("data/dim_corpus.db")
OUT_PATH = Path("site/data/corpus_cards.json")


def dominant_stance(con, debate_id: str) -> str:
    """Return the most common policy_stance across usable skeletons."""
    rows = con.execute(
        """SELECT policy_stance, count(*) as n
           FROM skeletons
           WHERE debate_id = ? AND usable_argument = 1 AND policy_stance IS NOT NULL
           GROUP BY policy_stance ORDER BY n DESC LIMIT 1""",
        (debate_id,),
    ).fetchone()
    return rows["policy_stance"] if rows else "unknown"


def top_techniques(profile_json: dict, n: int = 3) -> list[dict]:
    """Return the n most-detected techniques from a profile's dialectical_conduct."""
    techniques = profile_json.get("dialectical_conduct", {}).get("techniques", [])
    # already sorted by count descending from assemble_profile.py
    return [
        {"name": t["type"].replace("_", " "), "group": t["classifier_group"], "count": t["count"]}
        for t in techniques[:n]
    ]


def build(db_path: Path) -> list[dict]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    rows = con.execute("""
        SELECT d.debate_id,
               d.video_title,
               d.source_url,
               d.discourse_mode,
               length(d.transcript_text) AS chars,
               p.claim_count,
               p.profile_json,
               ds.overall_topic,
               ds.agreement_reached,
               ds.consensus_reached,
               ds.discourse_mode AS ds_mode
        FROM debates d
        JOIN profiles p ON p.debate_id = d.debate_id
        LEFT JOIN discourse_skeletons ds ON ds.debate_id = d.debate_id
        ORDER BY d.video_title
    """).fetchall()

    cards = []
    for r in rows:
        pj = json.loads(r["profile_json"])
        conduct = pj.get("dialectical_conduct", {})

        # Compute a simple rhetorical_density signal: negative detections per usable unit.
        # This is more interpretable than a raw count.
        unit_count = pj.get("unit_count", 1) or 1
        neg = conduct.get("negative_count", 0)
        pos = conduct.get("positive_count", 0)
        total = conduct.get("total_detections", 0)
        rhetorical_density = round(neg / unit_count, 3)

        # Full techniques list with evidence quotes for the expanded card panel
        all_techniques = [
            {
                "name":     t["type"].replace("_", " "),
                "group":    t["classifier_group"],
                "count":    t["count"],
                "polarity": t.get("polarity", ""),
                "quotes":   [e["evidence"] for e in t.get("examples", []) if e.get("evidence")],
            }
            for t in conduct.get("techniques", [])
        ]

        cards.append({
            "debate_id":          r["debate_id"],
            "title":              r["video_title"] or r["debate_id"],
            "source_url":         r["source_url"] or "",
            "discourse_mode":     r["ds_mode"] or r["discourse_mode"] or "unknown",
            "stance":             dominant_stance(con, r["debate_id"]),
            "chars":              r["chars"],
            "claim_count":        r["claim_count"] or 0,
            "total_detections":   total,
            "negative_count":     neg,
            "positive_count":     pos,
            "rhetorical_density": rhetorical_density,
            "agreement":          r["agreement_reached"] or "unknown",
            "consensus":          r["consensus_reached"] or "unknown",
            "overall_topic":      r["overall_topic"] or "",
            "top_techniques":     top_techniques(pj),
            "all_techniques":     all_techniques,
        })

    # Sort by rhetorical_density signal descending so the most aggressive debates come first
    cards.sort(key=lambda c: -c["rhetorical_density"])
    return cards


def main():
    parser = argparse.ArgumentParser(description="Build corpus cards JSON for the DIM site")
    parser.add_argument("--db",  type=Path, default=DB_PATH)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")

    cards = build(args.db)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(cards, indent=2))

    print(f"Written {args.out}")
    print(f"  {len(cards)} debate cards")
    for c in cards[:5]:
        print(f"  [{c['stance']:<8}] rhetorical_density={c['rhetorical_density']:.3f}  {c['title'][:55]}")


if __name__ == "__main__":
    main()
