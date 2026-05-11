#!/usr/bin/env python3
"""
Generate a readable HTML browser for pipeline/taxonomy.json.
"""

from __future__ import annotations

import json
from collections import Counter
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TAXONOMY_PATH = ROOT / "pipeline" / "taxonomy.json"
OUTPUT_PATH = ROOT / "site" / "taxonomy.html"


def badge(text: str, cls: str = "") -> str:
    cls_attr = f" class=\"badge {cls}\"" if cls else " class=\"badge\""
    return f"<span{cls_attr}>{escape(text)}</span>"


def list_badges(values) -> str:
    if not values:
        return "<span class=\"muted\">None</span>"
    return "".join(badge(str(v)) for v in values)


def render_examples(examples) -> str:
    if not examples:
        return "<p class=\"muted\">No examples recorded.</p>"
    parts = []
    for example in examples:
        text = escape(example.get("text", ""))
        source = escape(example.get("source", "Unknown source"))
        issue = escape(example.get("issue", "Unknown issue"))
        parts.append(
            f"""
            <article class="example-card">
              <p class="example-text">{text}</p>
              <p class="example-meta"><strong>Source:</strong> {source}</p>
              <p class="example-meta"><strong>Issue:</strong> {issue}</p>
            </article>
            """
        )
    return "\n".join(parts)


def render_row(entry: dict) -> str:
    aliases = ", ".join(entry.get("aliases", [])) or "—"
    group = entry.get("classifier_group") or "—"
    prov = entry.get("provenance", "established")
    examples = entry.get("examples", [])
    details = f"""
    <div class="details-grid">
      <section>
        <h4>Aliases</h4>
        <p>{escape(aliases)}</p>
      </section>
      <section>
        <h4>Distinguishing Features</h4>
        <p>{escape(entry.get("distinguishing_features", "—"))}</p>
      </section>
      <section>
        <h4>Distinguishes From</h4>
        <div class="badge-wrap">{list_badges(entry.get("distinguishes_from", []))}</div>
      </section>
      <section>
        <h4>Common Co-occurrences</h4>
        <div class="badge-wrap">{list_badges(entry.get("common_cooccurrences", []))}</div>
      </section>
      <section>
        <h4>Crossover Debate Terminology</h4>
        <div class="badge-wrap">{list_badges(entry.get("crossover_debate_terminology", []))}</div>
      </section>
      <section>
        <h4>Examples</h4>
        <div class="examples">{render_examples(examples)}</div>
      </section>
    </div>
    """
    search_blob = " | ".join(
        [
            entry.get("id", ""),
            entry.get("name", ""),
            entry.get("category", ""),
            entry.get("era", ""),
            group,
            prov,
            " ".join(entry.get("aliases", [])),
            entry.get("definition", ""),
            entry.get("distinguishing_features", ""),
            " ".join(entry.get("distinguishes_from", [])),
            " ".join(entry.get("common_cooccurrences", [])),
            " ".join(entry.get("crossover_debate_terminology", [])),
        ]
    )
    return f"""
    <tr data-search="{escape(search_blob.lower())}" data-category="{escape(entry.get('category', '').lower())}" data-era="{escape(entry.get('era', '').lower())}" data-group="{escape(group.lower())}" data-provenance="{escape(prov.lower())}">
      <td class="sticky-name">
        <details>
          <summary>
            <span class="entry-name">{escape(entry.get("name", ""))}</span>
            <span class="entry-id">{escape(entry.get("id", ""))}</span>
          </summary>
          {details}
        </details>
      </td>
      <td>{escape(entry.get("category", "—"))}</td>
      <td>{escape(group)}</td>
      <td>{escape(entry.get("era", "—"))}</td>
      <td>{escape(prov)}</td>
      <td>{escape(aliases)}</td>
      <td>{escape(entry.get("definition", ""))}</td>
      <td>{len(examples)}</td>
    </tr>
    """


def options(values) -> str:
    items = ['<option value="">All</option>']
    for value in sorted(v for v in values if v):
        items.append(f"<option value=\"{escape(value.lower())}\">{escape(value)}</option>")
    return "\n".join(items)


def build_html(entries: list[dict]) -> str:
    categories = Counter(entry.get("category", "unknown") for entry in entries)
    eras = Counter(entry.get("era", "unknown") for entry in entries)
    groups = Counter(entry.get("classifier_group") or "ungrouped" for entry in entries)
    provenance = Counter(entry.get("provenance", "established") for entry in entries)

    rows = "\n".join(render_row(entry) for entry in entries)

    summary_cards = [
        ("Entries", str(len(entries))),
        ("Categories", str(len(categories))),
        ("Classifier Groups", str(len(groups))),
        ("Coined Entries", str(provenance.get("coined", 0))),
    ]

    summary_html = "\n".join(
        f'<article class="summary-card"><h3>{escape(label)}</h3><p>{escape(value)}</p></article>'
        for label, value in summary_cards
    )

    breakdown_html = f"""
    <section class="breakdowns">
      <div>
        <h3>By Category</h3>
        <ul>{"".join(f"<li><strong>{escape(k)}</strong>: {v}</li>" for k, v in sorted(categories.items()))}</ul>
      </div>
      <div>
        <h3>By Classifier Group</h3>
        <ul>{"".join(f"<li><strong>{escape(k)}</strong>: {v}</li>" for k, v in sorted(groups.items()))}</ul>
      </div>
      <div>
        <h3>By Era</h3>
        <ul>{"".join(f"<li><strong>{escape(k)}</strong>: {v}</li>" for k, v in sorted(eras.items()))}</ul>
      </div>
      <div>
        <h3>By Provenance</h3>
        <ul>{"".join(f"<li><strong>{escape(k)}</strong>: {v}</li>" for k, v in sorted(provenance.items()))}</ul>
      </div>
    </section>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DIM Taxonomy Browser</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --panel: #fffaf2;
      --ink: #1f1a17;
      --muted: #6f655d;
      --line: #d7c9b7;
      --accent: #a3472f;
      --accent-soft: #f3dfd2;
      --badge: #efe6d7;
      --shadow: 0 18px 40px rgba(74, 46, 22, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(163,71,47,0.12), transparent 28%),
        linear-gradient(180deg, #f7f1e8 0%, var(--bg) 100%);
    }}
    .page {{
      max-width: 1500px;
      margin: 0 auto;
      padding: 40px 24px 64px;
    }}
    .hero {{
      padding: 28px;
      border: 1px solid var(--line);
      background: var(--panel);
      box-shadow: var(--shadow);
      border-radius: 24px;
      margin-bottom: 24px;
    }}
    h1, h2, h3, h4 {{ margin: 0 0 12px; line-height: 1.1; }}
    h1 {{ font-size: clamp(2rem, 4vw, 3.8rem); }}
    h2 {{ font-size: 1.4rem; margin-top: 24px; }}
    p {{ line-height: 1.55; }}
    .muted {{ color: var(--muted); }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin: 22px 0 18px;
    }}
    .summary-card {{
      background: linear-gradient(180deg, #fffdf9 0%, #f9f2e9 100%);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
    }}
    .summary-card p {{
      font-size: 2rem;
      font-weight: 700;
      margin: 0;
      color: var(--accent);
    }}
    .breakdowns {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin-top: 18px;
    }}
    .breakdowns > div {{
      background: rgba(255,255,255,0.65);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
    }}
    .breakdowns ul {{
      margin: 0;
      padding-left: 18px;
    }}
    .controls {{
      display: grid;
      grid-template-columns: 2fr repeat(4, minmax(140px, 1fr));
      gap: 12px;
      margin: 26px 0 16px;
    }}
    .controls label {{
      display: block;
      font-size: 0.85rem;
      margin-bottom: 6px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .controls input, .controls select {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #fffdf8;
      font: inherit;
      color: var(--ink);
    }}
    .table-wrap {{
      border: 1px solid var(--line);
      border-radius: 22px;
      overflow: hidden;
      background: var(--panel);
      box-shadow: var(--shadow);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      padding: 14px 12px;
      text-align: left;
      font-size: 0.95rem;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #efe4d3;
      z-index: 1;
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    td {{ background: rgba(255,255,255,0.68); }}
    tr.hidden {{ display: none; }}
    details > summary {{
      cursor: pointer;
      list-style: none;
    }}
    details > summary::-webkit-details-marker {{ display: none; }}
    .entry-name {{
      display: block;
      font-weight: 700;
      margin-bottom: 4px;
    }}
    .entry-id {{
      color: var(--accent);
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: 0.82rem;
    }}
    .details-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 14px;
      margin-top: 14px;
      padding: 14px;
      background: #fff8ee;
      border: 1px solid var(--line);
      border-radius: 14px;
    }}
    .details-grid h4 {{
      font-size: 0.9rem;
      color: var(--accent);
    }}
    .badge-wrap {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .badge {{
      display: inline-block;
      background: var(--badge);
      border: 1px solid var(--line);
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 0.8rem;
      margin: 0 6px 6px 0;
    }}
    .example-card {{
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
      background: rgba(255,255,255,0.8);
      margin-bottom: 10px;
    }}
    .example-text {{ margin: 0 0 8px; }}
    .example-meta {{
      margin: 2px 0;
      font-size: 0.86rem;
      color: var(--muted);
    }}
    .footer-note {{
      margin-top: 16px;
      font-size: 0.9rem;
      color: var(--muted);
    }}
    @media (max-width: 1100px) {{
      .controls {{
        grid-template-columns: 1fr 1fr;
      }}
    }}
    @media (max-width: 720px) {{
      .page {{ padding: 20px 14px 42px; }}
      .controls {{ grid-template-columns: 1fr; }}
      th, td {{ padding: 12px 10px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <p class="muted">Discourse Integrity Map</p>
      <h1>Taxonomy Browser</h1>
      <nav style="font-size:0.85rem;margin-top:12px;margin-bottom:4px">
        <a href="map.html" style="color:var(--accent);text-decoration:none;margin-right:18px">Map</a>
        <a href="sunburst.html" style="color:var(--accent);text-decoration:none;margin-right:18px">Sunburst</a>
        <a href="heatmap.html" style="color:var(--accent);text-decoration:none;margin-right:18px">Heatmap</a>
        <a href="corpus.html" style="color:var(--accent);text-decoration:none;margin-right:18px">Corpus</a>
        <a href="positions.html" style="color:var(--accent);text-decoration:none;margin-right:18px">Agora</a>
        <a href="debate.html" style="color:var(--accent);text-decoration:none;margin-right:18px">Debate</a>
        <a href="traditions.html" style="color:var(--accent);text-decoration:none;margin-right:18px">Traditions</a>
      </nav>
      <p>This page turns <code>pipeline/taxonomy.json</code> into a readable reference. Every field from each entry is preserved. The table gives you the whole landscape at a glance; open any entry to see its full detail, adjacent distinctions, co-occurrences, and examples.</p>
      <div class="summary-grid">
        {summary_html}
      </div>
      {breakdown_html}
    </section>

    <section class="controls" aria-label="Filters">
      <div>
        <label for="search">Search</label>
        <input id="search" type="search" placeholder="Search names, ids, aliases, definitions, examples-adjacent fields">
      </div>
      <div>
        <label for="category-filter">Category</label>
        <select id="category-filter">{options(categories.keys())}</select>
      </div>
      <div>
        <label for="group-filter">Classifier Group</label>
        <select id="group-filter">{options(groups.keys())}</select>
      </div>
      <div>
        <label for="era-filter">Era</label>
        <select id="era-filter">{options(eras.keys())}</select>
      </div>
      <div>
        <label for="prov-filter">Provenance</label>
        <select id="prov-filter">{options(provenance.keys())}</select>
      </div>
    </section>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Name / ID</th>
            <th>Category</th>
            <th>Classifier Group</th>
            <th>Era</th>
            <th>Provenance</th>
            <th>Aliases</th>
            <th>Definition</th>
            <th>Examples</th>
          </tr>
        </thead>
        <tbody id="taxonomy-body">
          {rows}
        </tbody>
      </table>
    </div>
    <p class="footer-note">Tip: use the filters to shrink the field, then expand entries one by one. This is especially helpful for seeing how coined terms sit alongside established ones, or how categories map onto classifier groups.</p>
  </main>
  <script>
    const rows = [...document.querySelectorAll('#taxonomy-body tr')];
    const search = document.getElementById('search');
    const categoryFilter = document.getElementById('category-filter');
    const groupFilter = document.getElementById('group-filter');
    const eraFilter = document.getElementById('era-filter');
    const provFilter = document.getElementById('prov-filter');

    function applyFilters() {{
      const term = search.value.trim().toLowerCase();
      const category = categoryFilter.value;
      const group = groupFilter.value;
      const era = eraFilter.value;
      const provenance = provFilter.value;

      rows.forEach((row) => {{
        const matchesSearch = !term || row.dataset.search.includes(term);
        const matchesCategory = !category || row.dataset.category === category;
        const matchesGroup = !group || row.dataset.group === group;
        const matchesEra = !era || row.dataset.era === era;
        const matchesProvenance = !provenance || row.dataset.provenance === provenance;
        row.classList.toggle('hidden', !(matchesSearch && matchesCategory && matchesGroup && matchesEra && matchesProvenance));
      }});
    }}

    [search, categoryFilter, groupFilter, eraFilter, provFilter].forEach((el) => {{
      el.addEventListener('input', applyFilters);
      el.addEventListener('change', applyFilters);
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    entries = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_html(entries), encoding="utf-8")
    print(f"Built {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
