#!/usr/bin/env python3
"""
Output persistence helpers for the DIM pipeline.
"""

import json
import sys
from pathlib import Path


def load_existing(output_path: Path) -> list[dict]:
    if output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    return []


def save_output(result: dict, output_path: Path, append: bool = True) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if append:
        existing = load_existing(output_path)
        existing.append(result)
        data = existing
    else:
        data = [result]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {output_path}", file=sys.stderr)
