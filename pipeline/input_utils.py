#!/usr/bin/env python3
"""
Input and text-loading helpers for the DIM pipeline.
"""

import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self):
        return " ".join(self._parts)


def strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return re.sub(r"\s+", " ", stripper.get_text()).strip()


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        sys.exit(f"Could not fetch URL: {e}")
    return strip_html(raw)


def get_text(source: str) -> tuple[str, str]:
    if source.startswith("http://") or source.startswith("https://"):
        print(f"Fetching: {source}", file=sys.stderr)
        return fetch_url(source), source

    path = Path(source)
    if path.exists():
        return path.read_text(encoding="utf-8"), str(path)

    return source, "pasted text"
