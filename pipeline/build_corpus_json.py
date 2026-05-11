#!/usr/bin/env python3
"""
build_corpus_json.py

Generates site/data/corpus.json for the map visualisation.
Reads from the SQLite corpus database.

Usage:
    python3 pipeline/build_corpus_json.py
    python3 pipeline/build_corpus_json.py --db data/dim_corpus.db
"""

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

DB_PATH  = Path("data/dim_corpus.db")
OUT_PATH = Path("site/data/corpus.json")


def query(con, sql, params=()):
    return con.execute(sql, params).fetchall()


def dominant_stance(stance_counts: dict) -> str:
    if not stance_counts:
        return "neutral"
    return max(stance_counts, key=stance_counts.get)


def build(db_path: Path) -> dict:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    # ── Debates that have at least one profile ────────────────────────────────
    profiled = {
        r["debate_id"] for r in query(con, "SELECT DISTINCT debate_id FROM profiles")
    }

    debate_rows = query(con, """
        SELECT d.debate_id, d.video_title, d.discourse_mode, d.speaker_count,
               d.published_date, d.source_url
        FROM debates d
        WHERE d.debate_id IN ({})
    """.format(",".join("?" * len(profiled))), list(profiled))

    # ── Skeleton stance counts per debate ─────────────────────────────────────
    sk_rows = query(con, """
        SELECT debate_id, policy_stance, count(*) as n
        FROM skeletons
        WHERE usable_argument = 1 AND policy_stance IS NOT NULL
        GROUP BY debate_id, policy_stance
    """)
    stance_counts_by_debate = defaultdict(dict)
    for r in sk_rows:
        stance_counts_by_debate[r["debate_id"]][r["policy_stance"]] = r["n"]

    # ── Unit counts per debate ────────────────────────────────────────────────
    unit_count_rows = query(con, """
        SELECT debate_id, count(*) as n FROM units GROUP BY debate_id
    """)
    unit_counts = {r["debate_id"]: r["n"] for r in unit_count_rows}

    # ── Detection counts per debate ───────────────────────────────────────────
    det_count_rows = query(con, """
        SELECT debate_id,
               count(*) as total,
               sum(CASE WHEN polarity='negative' THEN 1 ELSE 0 END) as neg,
               sum(CASE WHEN polarity='positive' THEN 1 ELSE 0 END) as pos
        FROM detections
        GROUP BY debate_id
    """)
    det_counts = {
        r["debate_id"]: {"total": r["total"], "neg": r["neg"], "pos": r["pos"]}
        for r in det_count_rows
    }

    # ── Common ground & participants from discourse_skeletons ─────────────────
    ds_rows = query(con, """
        SELECT debate_id, common_ground, participants
        FROM discourse_skeletons
    """)
    ds_by_debate = {}
    for r in ds_rows:
        try:
            cg = json.loads(r["common_ground"]) if r["common_ground"] else []
        except (json.JSONDecodeError, TypeError):
            cg = []
        try:
            parts = json.loads(r["participants"]) if r["participants"] else []
        except (json.JSONDecodeError, TypeError):
            parts = []
        # Take the first discourse_skeleton per debate (most debates have one)
        if r["debate_id"] not in ds_by_debate:
            ds_by_debate[r["debate_id"]] = {"common_ground": cg, "participants": parts}

    # ── Build debates list ────────────────────────────────────────────────────
    debates = []
    for row in debate_rows:
        did = row["debate_id"]
        sc  = stance_counts_by_debate.get(did, {})
        dc  = det_counts.get(did, {"total": 0, "neg": 0, "pos": 0})
        ds  = ds_by_debate.get(did, {"common_ground": [], "participants": []})

        debates.append({
            "id":             did,
            "title":          row["video_title"] or "Untitled",
            "discourse_mode": row["discourse_mode"] or "unknown",
            "speaker_count":  row["speaker_count"] or 0,
            "published_date": row["published_date"] or "",
            "source_url":     row["source_url"] or "",
            "unit_count":     unit_counts.get(did, 0),
            "detection_count": dc["total"],
            "neg_count":      dc["neg"],
            "pos_count":      dc["pos"],
            "stance":         dominant_stance(sc),
            "stance_counts":  sc,
            "common_ground":  ds["common_ground"],
            "participants":   ds["participants"],
        })

    # Sort by detection count desc
    debates.sort(key=lambda d: -d["detection_count"])

    # ── Units ─────────────────────────────────────────────────────────────────
    unit_rows = query(con, """
        SELECT u.unit_id, u.debate_id, u.unit_index, u.unit_type,
               u.main_issue, u.speakers,
               s.policy_stance, s.skeleton_id,
               count(d.detection_id) as detection_count
        FROM units u
        LEFT JOIN skeletons s ON s.unit_id = u.unit_id AND s.usable_argument = 1
        LEFT JOIN detections d ON d.skeleton_id = s.skeleton_id
        WHERE u.debate_id IN ({})
        GROUP BY u.unit_id
    """.format(",".join("?" * len(profiled))), list(profiled))

    units = []
    for r in unit_rows:
        try:
            speakers = json.loads(r["speakers"]) if r["speakers"] else []
        except (json.JSONDecodeError, TypeError):
            speakers = []
        units.append({
            "id":             r["unit_id"],
            "debate_id":      r["debate_id"],
            "index":          r["unit_index"],
            "type":           r["unit_type"] or "unit",
            "main_issue":     r["main_issue"] or "",
            "policy_stance":  r["policy_stance"] or "neutral",
            "skeleton_id":    r["skeleton_id"],
            "detection_count": r["detection_count"] or 0,
        })

    # ── Detections ────────────────────────────────────────────────────────────
    all_det_rows = query(con, """
        SELECT detection_id, unit_id, debate_id,
               technique_type, classifier_group, confidence,
               evidence, era, polarity
        FROM detections
        WHERE debate_id IN ({})
    """.format(",".join("?" * len(profiled))), list(profiled))

    detections = [
        {
            "id":         r["detection_id"],
            "unit_id":    r["unit_id"],
            "debate_id":  r["debate_id"],
            "type":       r["technique_type"],
            "group":      r["classifier_group"] or "ungrouped",
            "polarity":   r["polarity"],
            "confidence": r["confidence"],
            "evidence":   r["evidence"] or "",
            "era":        r["era"] or "",
        }
        for r in all_det_rows
    ]

    # ── Common-ground links between debates ───────────────────────────────────
    # Simple keyword overlap between common_ground items across debate pairs
    cg_links = []
    debate_cg = {d["id"]: d["common_ground"] for d in debates if d["common_ground"]}
    debate_ids = list(debate_cg.keys())

    for i, a_id in enumerate(debate_ids):
        for b_id in debate_ids[i+1:]:
            shared = []
            for a_item in debate_cg[a_id]:
                a_words = set(a_item.lower().split())
                for b_item in debate_cg[b_id]:
                    b_words = set(b_item.lower().split())
                    common_words = (a_words & b_words) - {
                        "a", "an", "the", "is", "are", "of", "and", "to",
                        "in", "that", "it", "for", "on", "with", "as", "by",
                        "this", "or", "be", "has", "not", "at", "from",
                    }
                    if len(common_words) >= 3:
                        shared.append({"a": a_item, "b": b_item,
                                       "shared_words": sorted(common_words)[:5]})
            if shared:
                strength = min(len(shared) / 10, 1.0)
                cg_links.append({
                    "source":       a_id,
                    "target":       b_id,
                    "strength":     round(strength, 3),
                    "shared_items": shared[:4],
                })

    return {
        "debates":    debates,
        "units":      units,
        "detections": detections,
        "cg_links":   cg_links,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    data = build(args.db)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2))

    print(f"Written {args.out}")
    print(f"  Debates:    {len(data['debates'])}")
    print(f"  Units:      {len(data['units'])}")
    print(f"  Detections: {len(data['detections'])}")
    print(f"  CG links:   {len(data['cg_links'])}")


if __name__ == "__main__":
    main()
