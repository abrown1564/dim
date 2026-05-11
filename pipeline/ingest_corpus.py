#!/usr/bin/env python3
"""
Ingest extracted transcript files into the DIM SQLite corpus database.

Usage:
    python pipeline/ingest_corpus.py <transcript_dir> [--db data/dim_corpus.db] [--dry-run]

Each file must follow the standard header format produced by ingest_youtube.py.
Files that have already been ingested (matched by source_url or file path) are skipped.
"""

import argparse
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS debates (
    debate_id       TEXT PRIMARY KEY,
    source_file     TEXT,
    source_name     TEXT,
    channel_id      TEXT,
    channel_url     TEXT,
    video_title     TEXT,
    source_url      TEXT,
    source_prefix   TEXT,
    reliability     TEXT,
    published_date  TEXT,
    date_status     TEXT,
    content_form    TEXT,
    discourse_mode  TEXT,
    suggested_code  TEXT,
    transcript_method TEXT,
    speaker_count   INTEGER,
    extracted_date  TEXT,
    chunking_hints  TEXT,
    description     TEXT,
    source_platform TEXT,
    source_platform_id TEXT,
    transcript_path TEXT,
    transcript_text TEXT,
    ingested_at     TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_source_url ON debates(source_url);
CREATE UNIQUE INDEX IF NOT EXISTS idx_transcript_path ON debates(transcript_path);
CREATE INDEX IF NOT EXISTS idx_discourse_mode ON debates(discourse_mode);
CREATE INDEX IF NOT EXISTS idx_reliability ON debates(reliability);
CREATE INDEX IF NOT EXISTS idx_published_date ON debates(published_date);
CREATE INDEX IF NOT EXISTS idx_source_platform ON debates(source_platform);
"""

SEPARATOR = "=" * 60
HEADER_PATTERN = re.compile(r"^([A-Z ]+?)\s*:\s*(.*)$")


def parse_file(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="replace")

    if SEPARATOR not in text:
        return None

    header_block, _, transcript_text = text.partition(SEPARATOR)
    transcript_text = transcript_text.strip()

    meta = {}
    for line in header_block.splitlines():
        m = HEADER_PATTERN.match(line)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip()
            meta[key] = value

    if not meta:
        return None

    # Parse speaker count out of TRANSCRIPT field
    # e.g. "pyannote.audio diarisation + Whisper (3 speaker(s) detected)"
    speaker_count = None
    transcript_method = meta.get("TRANSCRIPT", "")
    sc_match = re.search(r"\((\d+)\s+speaker", transcript_method)
    if sc_match:
        speaker_count = int(sc_match.group(1))

    # Derive platform and platform-native ID from URL
    source_url = meta.get("VIDEO URL", meta.get("SOURCE URL", ""))
    source_platform, source_platform_id = _parse_platform(source_url)

    return {
        "debate_id":          str(uuid.uuid4()),
        "source_file":        meta.get("SOURCE FILE"),
        "source_name":        meta.get("SOURCE NAME"),
        "channel_id":         meta.get("CHANNEL ID"),
        "channel_url":        meta.get("CHANNEL URL"),
        "video_title":        meta.get("VIDEO TITLE"),
        "source_url":         source_url or None,
        "source_prefix":      meta.get("SOURCE PREFIX"),
        "reliability":        meta.get("RELIABILITY"),
        "published_date":     meta.get("PUBLISHED DATE"),
        "date_status":        meta.get("DATE STATUS"),
        "content_form":       meta.get("CONTENT FORM"),
        "discourse_mode":     meta.get("DISCOURSE MODE"),
        "suggested_code":     meta.get("SUGGESTED CODE"),
        "transcript_method":  transcript_method or None,
        "speaker_count":      speaker_count,
        "extracted_date":     meta.get("EXTRACTED"),
        "chunking_hints":     meta.get("CHUNKING HINTS"),
        "description":        meta.get("DESCRIPTION"),
        "source_platform":    source_platform,
        "source_platform_id": source_platform_id,
        "transcript_path":    str(path.resolve()),
        "transcript_text":    transcript_text,
        "ingested_at":        datetime.now(timezone.utc).isoformat(),
    }


def _parse_platform(url: str) -> tuple[str | None, str | None]:
    if not url:
        return None, None
    if "youtube.com" in url or "youtu.be" in url:
        m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
        if not m:
            m = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
        return "youtube", m.group(1) if m else None
    if "loom.com" in url:
        m = re.search(r"loom\.com/share/([a-f0-9]+)", url)
        return "loom", m.group(1) if m else None
    return "other", None


def ingest_directory(transcript_dir: Path, db_path: Path, dry_run: bool = False):
    files = sorted(transcript_dir.rglob("*_extracted_txt.txt"))
    if not files:
        print(f"No transcript files found in {transcript_dir}")
        return

    if not dry_run:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(db_path)
        con.executescript(DB_SCHEMA)
        con.commit()

    inserted = skipped = errors = 0

    for f in files:
        try:
            record = parse_file(f)
            if record is None:
                print(f"  [skip] No header found: {f.name}")
                skipped += 1
                continue

            if dry_run:
                print(f"  [dry]  {record['video_title'] or f.name}  "
                      f"| {record['discourse_mode']} | {record['speaker_count']} speakers "
                      f"| {record['source_platform']}")
                inserted += 1
                continue

            try:
                con.execute(
                    """INSERT INTO debates VALUES (
                        :debate_id, :source_file, :source_name, :channel_id,
                        :channel_url, :video_title, :source_url, :source_prefix,
                        :reliability, :published_date, :date_status, :content_form,
                        :discourse_mode, :suggested_code, :transcript_method,
                        :speaker_count, :extracted_date, :chunking_hints,
                        :description, :source_platform, :source_platform_id,
                        :transcript_path, :transcript_text, :ingested_at
                    )""",
                    record,
                )
                con.commit()
                print(f"  [ok]   {record['video_title'] or f.name}  → {record['debate_id']}")
                inserted += 1
            except sqlite3.IntegrityError:
                print(f"  [skip] Already ingested: {f.name}")
                skipped += 1

        except Exception as e:
            print(f"  [err]  {f.name}: {e}")
            errors += 1

    if not dry_run:
        con.close()

    print(f"\nDone — inserted: {inserted}, skipped: {skipped}, errors: {errors}")
    if not dry_run:
        print(f"Database: {db_path}")


def main():
    parser = argparse.ArgumentParser(description="Ingest transcript files into DIM corpus DB")
    parser.add_argument("transcript_dir", type=Path, help="Directory containing *_extracted_txt.txt files")
    parser.add_argument("--db", type=Path, default=Path("data/dim_corpus.db"), help="SQLite database path")
    parser.add_argument("--dry-run", action="store_true", help="Parse and print without writing to DB")
    args = parser.parse_args()

    if not args.transcript_dir.exists():
        print(f"Directory not found: {args.transcript_dir}")
        return

    ingest_directory(args.transcript_dir, args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
