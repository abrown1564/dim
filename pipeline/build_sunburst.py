#!/usr/bin/env python3
"""
build_sunburst.py

Generates the two hardcoded DATA_BY_STANCE and DATA_BY_GROUP constants
used by site/sunburst.html, reading from the SQLite corpus database.

Patches the constants directly into sunburst.html in-place.

Usage:
    python3 pipeline/build_sunburst.py
    python3 pipeline/build_sunburst.py --db data/dim_corpus.db
"""

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

DB_PATH      = Path("data/dim_corpus.db")
SUNBURST_PATH = Path("site/sunburst.html")

STANCES = ["anti", "pro", "mixed", "neutral"]
GROUP_ORDER = [
    "psychological_rhetoric",
    "evidence_quality",
    "semantic_manipulation",
    "formal_structure",
    "source_attacks",
    "counter_techniques",
]


def build_by_stance(rows):
    """stance → group → technique → count"""
    tree = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for technique, group, stance in rows:
        tree[stance][group][technique] += 1

    children = []
    for stance in STANCES:
        if stance not in tree:
            continue
        group_nodes = []
        for group in GROUP_ORDER:
            if group not in tree[stance]:
                continue
            techs = sorted(tree[stance][group].items(), key=lambda x: -x[1])
            tech_nodes = [{"name": t.replace("_", " "), "value": v} for t, v in techs]
            group_nodes.append({"name": group.replace("_", " "), "children": tech_nodes})
        children.append({"name": stance, "children": group_nodes})
    return {"name": "corpus", "children": children}


def build_by_group(rows):
    """group → technique → stance → count"""
    tree = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for technique, group, stance in rows:
        tree[group][technique][stance] += 1

    children = []
    for group in GROUP_ORDER:
        if group not in tree:
            continue
        tech_nodes = []
        for technique, stance_counts in sorted(tree[group].items(),
                                               key=lambda x: -sum(x[1].values())):
            stance_nodes = [
                {"name": s, "value": stance_counts[s]}
                for s in STANCES if s in stance_counts
            ]
            tech_nodes.append({"name": technique.replace("_", " "), "children": stance_nodes})
        children.append({"name": group.replace("_", " "), "children": tech_nodes})
    return {"name": "corpus", "children": children}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()

    con = sqlite3.connect(args.db)
    rows = con.execute("""
        SELECT d.technique_type, d.classifier_group, s.policy_stance
        FROM detections d
        JOIN skeletons s ON s.skeleton_id = d.skeleton_id
        WHERE s.policy_stance IS NOT NULL
          AND s.usable_argument = 1
          AND d.classifier_group IS NOT NULL
    """).fetchall()

    n_debates = con.execute(
        "SELECT count(DISTINCT debate_id) FROM detections"
    ).fetchone()[0]

    by_stance = build_by_stance(rows)
    by_group  = build_by_group(rows)

    html = SUNBURST_PATH.read_text()

    # Update debate count in subtitle
    html = re.sub(
        r'Rhetorical technique detections across \d+ debates',
        f'Rhetorical technique detections across {n_debates} debates',
        html
    )

    # Replace DATA_BY_STANCE constant
    html = re.sub(
        r'const DATA_BY_STANCE = \{.*?\};',
        f'const DATA_BY_STANCE = {json.dumps(by_stance, separators=(",", ":"))};',
        html, flags=re.DOTALL
    )

    # Replace DATA_BY_GROUP constant
    html = re.sub(
        r'const DATA_BY_GROUP = \{.*?\};',
        f'const DATA_BY_GROUP = {json.dumps(by_group, separators=(",", ":"))};',
        html, flags=re.DOTALL
    )

    SUNBURST_PATH.write_text(html)
    print(f"Updated sunburst.html — {len(rows)} detections across {n_debates} debates")


if __name__ == "__main__":
    main()
