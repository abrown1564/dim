#!/usr/bin/env python3
"""
DIM Full Pipeline Runner

Runs all 5 stages for a debate in sequence:
  1. detect_units      — segment transcript into argumentative units
  2. skeletonize_units — extract skeleton per unit
  3. merge_discourse   — merge into unified discourse skeleton
  4. classify_units    — rhetoric detection per unit
  5. assemble_profile  — score and assemble discourse profile

Usage:
    python pipeline/run_pipeline.py <debate_id> [--db data/dim_corpus.db] [--model claude-opus-4-7]
    python pipeline/run_pipeline.py --list
    python pipeline/run_pipeline.py --from-stage 3 <debate_id>   # resume from a stage
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import db
from detect_units      import detect_units
from skeletonize_units import skeletonize_debate
from merge_discourse   import merge_discourse
from classify_units    import classify_debate
from assemble_profile  import assemble_profile

STAGES = [
    (1, "Unit Detection",       detect_units),
    (2, "Unit Skeletonization", skeletonize_debate),
    (3, "Discourse Merge",      merge_discourse),
    (4, "Rhetoric Classification", classify_debate),
]


def run_pipeline(
    debate_id: str,
    model: str,
    db_path: Path,
    out_dir: Path,
    from_stage: int = 1,
) -> None:
    debate = db.get_debate(debate_id, db_path)
    if not debate:
        print(f"Debate not found: {debate_id}")
        print("Run: python pipeline/run_pipeline.py --list")
        return

    title = debate["video_title"] or debate_id
    print(f"\n{'='*60}")
    print(f"  DIM Pipeline — {title}")
    print(f"  Debate ID : {debate_id}")
    print(f"  Model     : {model}")
    print(f"{'='*60}")

    t_start = time.time()

    for stage_num, stage_label, stage_fn in STAGES:
        if stage_num < from_stage:
            print(f"\n  [Stage {stage_num}] {stage_label} — skipped")
            continue

        print(f"\n  [Stage {stage_num}/{len(STAGES)+1}] {stage_label}")
        t = time.time()
        try:
            result = stage_fn(debate_id, model, db_path)
            elapsed = round(time.time() - t, 1)
            print(f"  Time: {elapsed}s")
            if result is False:
                print(f"\n  ✗ Stage {stage_num} failed. Stopping.")
                return
            if result == 0 and stage_num < 4:
                print(f"\n  ✗ Stage {stage_num} produced no output. Stopping.")
                return
        except Exception as e:
            print(f"\n  ✗ Stage {stage_num} failed: {e}")
            raise

    # Stage 5 has different signature
    if from_stage <= 5:
        print(f"\n  [Stage 5/5] Profile Assembly")
        t = time.time()
        profile = assemble_profile(debate_id, db_path, out_dir)
        print(f"  Time: {round(time.time() - t, 1)}s")
        if not profile:
            print("  ✗ Profile assembly failed.")
            return

    total = round(time.time() - t_start, 1)
    print(f"\n{'='*60}")
    print(f"  Pipeline complete in {total}s")
    print(f"  Profile: {out_dir}/{title[:60]}.json")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Run the full DIM pipeline for a debate")
    parser.add_argument("debate_id", nargs="?", help="Debate UUID")
    parser.add_argument("--db",         type=Path, default=db.DB_PATH)
    parser.add_argument("--model",      default="claude-opus-4-7")
    parser.add_argument("--out",        type=Path, default=Path("data/profiles"))
    parser.add_argument("--from-stage", type=int,  default=1, help="Resume from stage N")
    parser.add_argument("--list",       action="store_true", help="List debates and exit")
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

    run_pipeline(
        debate_id=args.debate_id,
        model=args.model,
        db_path=args.db,
        out_dir=args.out,
        from_stage=args.from_stage,
    )


if __name__ == "__main__":
    main()
