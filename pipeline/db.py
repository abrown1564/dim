"""
Shared database utilities for the DIM pipeline.
All scripts import from here to ensure consistent schema and connection handling.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "dim_corpus.db"

MIGRATION = """
CREATE TABLE IF NOT EXISTS units (
    unit_id         TEXT PRIMARY KEY,
    debate_id       TEXT REFERENCES debates(debate_id),
    unit_index      INTEGER,
    unit_type       TEXT,
    main_issue      TEXT,
    speakers        TEXT,
    start_excerpt   TEXT,
    end_excerpt     TEXT,
    start_line      INTEGER,
    end_line        INTEGER,
    usable          INTEGER,
    reliability     TEXT,
    reason_if_low   TEXT,
    raw_yaml        TEXT,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS skeletons (
    skeleton_id              TEXT PRIMARY KEY,
    unit_id                  TEXT REFERENCES units(unit_id),
    debate_id                TEXT REFERENCES debates(debate_id),
    usable_argument          INTEGER,
    section_summary          TEXT,
    verbatim_excerpt         TEXT,
    stasis_points            TEXT,
    facts_to_verify          TEXT,
    assumptions_to_test      TEXT,
    terms_to_define          TEXT,
    policy_stance            TEXT,
    raw_yaml                 TEXT,
    created_at               TEXT
);

CREATE TABLE IF NOT EXISTS discourse_skeletons (
    ds_id                TEXT PRIMARY KEY,
    debate_id            TEXT REFERENCES debates(debate_id),
    discourse_mode       TEXT,
    overall_topic        TEXT,
    agreement_reached    TEXT,
    consensus_reached    TEXT,
    common_ground        TEXT,
    participants         TEXT,
    major_stasis_points  TEXT,
    facts_to_verify      TEXT,
    assumptions_to_test  TEXT,
    terms_to_define      TEXT,
    meta_comment         TEXT,
    raw_yaml             TEXT,
    created_at           TEXT
);

CREATE TABLE IF NOT EXISTS detections (
    detection_id      TEXT PRIMARY KEY,
    debate_id         TEXT REFERENCES debates(debate_id),
    unit_id           TEXT REFERENCES units(unit_id),
    skeleton_id       TEXT REFERENCES skeletons(skeleton_id),
    technique_type    TEXT,
    classifier_group  TEXT,
    confidence        REAL,
    evidence          TEXT,
    era               TEXT,
    polarity          TEXT,
    weighted_score    REAL,
    created_at        TEXT
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id         TEXT PRIMARY KEY,
    debate_id        TEXT REFERENCES debates(debate_id),
    unit_id          TEXT REFERENCES units(unit_id),
    skeleton_id      TEXT REFERENCES skeletons(skeleton_id),
    speaker          TEXT,
    claim_text       TEXT,
    stance           TEXT,
    stasis_type      TEXT,
    question_at_issue TEXT,
    warrant          TEXT,
    verbatim_excerpt TEXT,
    created_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_claims_debate  ON claims(debate_id);
CREATE INDEX IF NOT EXISTS idx_claims_unit    ON claims(unit_id);
CREATE INDEX IF NOT EXISTS idx_claims_speaker ON claims(speaker);

CREATE TABLE IF NOT EXISTS profiles (
    profile_id               TEXT PRIMARY KEY,
    debate_id                TEXT REFERENCES debates(debate_id),
    claim_count              INTEGER,
    negative_density         REAL,
    positive_density         REAL,
    net_score                REAL,
    eristic_signal_strength  REAL,
    profile_json             TEXT,
    created_at               TEXT
);

CREATE INDEX IF NOT EXISTS idx_units_debate    ON units(debate_id);
CREATE INDEX IF NOT EXISTS idx_skel_unit       ON skeletons(unit_id);
CREATE INDEX IF NOT EXISTS idx_skel_debate     ON skeletons(debate_id);
CREATE INDEX IF NOT EXISTS idx_det_debate      ON detections(debate_id);
CREATE INDEX IF NOT EXISTS idx_det_unit        ON detections(unit_id);
CREATE INDEX IF NOT EXISTS idx_profile_debate  ON profiles(debate_id);
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def migrate(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as con:
        con.executescript(MIGRATION)
        # Additive column migrations for existing databases
        for stmt in [
            "ALTER TABLE skeletons ADD COLUMN policy_stance TEXT",
        ]:
            try:
                con.execute(stmt)
            except Exception:
                pass
        con.commit()


def get_debate(debate_id: str, db_path: Path = DB_PATH) -> sqlite3.Row | None:
    with connect(db_path) as con:
        return con.execute(
            "SELECT * FROM debates WHERE debate_id = ?", (debate_id,)
        ).fetchone()


def list_debates(db_path: Path = DB_PATH) -> list[sqlite3.Row]:
    with connect(db_path) as con:
        return con.execute(
            "SELECT debate_id, video_title, discourse_mode, speaker_count FROM debates ORDER BY published_date"
        ).fetchall()
