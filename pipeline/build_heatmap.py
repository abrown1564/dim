#!/usr/bin/env python3
"""
build_heatmap.py

Generates site/data/heatmap.json for the technique × stance heatmap page.

The key analytical move here is NORMALISATION: we don't compare raw detection
counts across stances, because the corpus has more anti-wealth-tax content than
pro. Instead we divide by the number of usable units in each stance, giving a
rate (detections per unit). That makes anti and pro genuinely comparable.

Usage:
    python3 pipeline/build_heatmap.py
    python3 pipeline/build_heatmap.py --db data/dim_corpus.db
"""

import argparse
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

DB_PATH  = Path("data/dim_corpus.db")
OUT_PATH = Path("site/data/heatmap.json")

STANCES      = ["anti", "pro", "mixed", "neutral"]
GROUP_ORDER  = [
    "psychological_rhetoric",
    "evidence_quality",
    "semantic_manipulation",
    "formal_structure",
    "source_attacks",
    "counter_techniques",
]


def query(con, sql, params=()):
    return con.execute(sql, params).fetchall()


def build(db_path: Path) -> dict:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    # ── 1. usable unit count per stance ──────────────────────────────────────
    # We count skeletons (one per usable unit) rather than debates, so that a
    # long debate with 20 units isn't treated the same as a short one with 3.
    unit_rows = query(con, """
        SELECT policy_stance, count(*) as n
        FROM skeletons
        WHERE usable_argument = 1
          AND policy_stance IS NOT NULL
        GROUP BY policy_stance
    """)
    unit_counts = {r["policy_stance"]: r["n"] for r in unit_rows}

    # ── 2. raw detection counts per (technique, group, stance) ───────────────
    det_rows = query(con, """
        SELECT d.technique_type,
               d.classifier_group,
               s.policy_stance,
               count(*) as n
        FROM detections d
        JOIN skeletons s ON s.skeleton_id = d.skeleton_id
        WHERE s.policy_stance IS NOT NULL
        GROUP BY d.technique_type, d.classifier_group, s.policy_stance
    """)

    # Build nested dict: group → technique → stance → count
    raw = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for r in det_rows:
        raw[r["classifier_group"]][r["technique_type"]][r["policy_stance"]] += r["n"]

    # ── 3. normalise to rates and find the global maximum ────────────────────
    # rate = detections / usable_units_in_that_stance
    # We use sqrt of rate for cell opacity so low-frequency techniques remain
    # visible rather than washing out to near-white.
    max_rate = 0.0
    groups = []

    for group_key in GROUP_ORDER:
        if group_key not in raw:
            continue
        techs = raw[group_key]

        technique_rows = []
        for tech_key, stance_counts in sorted(
            techs.items(),
            key=lambda kv: -sum(kv[1].values()),  # sort by total detections desc
        ):
            counts = {st: stance_counts.get(st, 0) for st in STANCES}
            total  = sum(counts.values())

            # rate: detections-per-unit for each stance
            rates = {}
            for st in STANCES:
                denom = unit_counts.get(st, 0)
                rates[st] = round(counts[st] / denom, 4) if denom else 0.0
                max_rate = max(max_rate, rates[st])

            technique_rows.append({
                "key":    tech_key,
                "name":   tech_key.replace("_", " "),
                "counts": counts,
                "rates":  rates,
                "total":  total,
            })

        groups.append({
            "key":        group_key,
            "name":       group_key.replace("_", " "),
            "techniques": technique_rows,
        })

    # ── 4. summary stats for the page header ─────────────────────────────────
    debate_count = query(con, "SELECT count(DISTINCT debate_id) FROM profiles")[0][0]
    detection_count = query(con, "SELECT count(*) FROM detections")[0][0]

    return {
        "stances":        STANCES,
        "unit_counts":    unit_counts,
        "max_rate":       round(max_rate, 4),
        "groups":         groups,
        "debate_count":   debate_count,
        "detection_count": detection_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Build heatmap JSON for the DIM site")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")

    data = build(args.db)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2))

    total_techs = sum(len(g["techniques"]) for g in data["groups"])
    print(f"Written {args.out}")
    print(f"  {data['debate_count']} debates · {data['detection_count']} detections · {total_techs} techniques")
    print(f"  Unit counts by stance: {data['unit_counts']}")
    print(f"  Max rate: {data['max_rate']:.4f}")


if __name__ == "__main__":
    main()
