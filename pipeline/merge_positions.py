"""
Merge first-prompt output (positions + shared, with claim/side/stasis/context)
with second-prompt output (source_indices, source_debates, example_quotes)
into a single clean claim_positions.json.

Frequency is replaced with len(source_indices) for precision.

NOTE: This script is corpus-specific. The FIRST_OUTPUT dict hardcodes the
canonical positions produced by the aggregation LLM prompt for the wealth-tax
corpus. To use this pipeline on a new topic, you would re-run the aggregation
prompt and update FIRST_OUTPUT accordingly — this file documents the methodology
and the expected data shape rather than providing a generic reusable tool.
"""

import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "site" / "data"

with open(DATA / "claims_index.json") as f:
    claims_index = json.load(f)  # 0-indexed; claim [N] is claims_index[N-1]

# First prompt output — canonical positions with metadata
FIRST_OUTPUT = {
    "positions": [
        {"label": "capital flight risk", "claim": "A wealth tax causes wealthy individuals and businesses to relocate, taking jobs and capital with them.", "side": "anti", "stasis": "fact", "context": "both"},
        {"label": "wealth taxes have failed elsewhere", "claim": "Most countries that tried wealth taxes (France, Germany, Sweden, Denmark) abandoned them because they did not work.", "side": "anti", "stasis": "fact", "context": "both"},
        {"label": "valuation and enforcement difficulty", "claim": "Valuing non-cash assets and enforcing a wealth tax is impractical, invasive, and administratively unworkable.", "side": "anti", "stasis": "procedure", "context": "both"},
        {"label": "double taxation objection", "claim": "Taxing wealth accumulated from already-taxed income is confiscatory double taxation.", "side": "anti", "stasis": "definition", "context": "both"},
        {"label": "trickle down to ordinary people", "claim": "A wealth tax intended for the very rich will inevitably reach ordinary asset-holders and force them to sell property.", "side": "anti", "stasis": "fact", "context": "both"},
        {"label": "rewards risk and hard work", "claim": "Wealth is earned through risk, hard work, and enterprise, so the wealthy deserve to keep it rather than be taxed further.", "side": "anti", "stasis": "value", "context": "both"},
        {"label": "cut waste not raise taxes", "claim": "Government should cut wasteful spending and manage existing resources better rather than impose new taxes.", "side": "anti", "stasis": "policy", "context": "both"},
        {"label": "annual wealth tax mechanically fails", "claim": "Annual wealth taxes fail because behaviour adjusts; only one-off surprise taxes can work.", "side": "anti", "stasis": "fact", "context": "UK"},
        {"label": "politics of envy", "claim": "Wealth tax advocacy is driven by jealousy and class warfare rather than economic principle.", "side": "anti", "stasis": "value", "context": "UK"},
        {"label": "revenue projections unrealistic", "claim": "Projected wealth tax revenues (e.g. £14.9bn) are magic-money-tree thinking unsupported by comparator countries.", "side": "anti", "stasis": "fact", "context": "UK"},
        {"label": "high earners already pay enough", "claim": "Wealthy individuals already pay 45% income tax and substantial amounts overall, so further taxation is unjustified.", "side": "anti", "stasis": "fact", "context": "UK"},
        {"label": "rising inequality harms society", "claim": "Wealth is increasingly concentrated at the top while wages stagnate, public services decline, and child poverty rises.", "side": "pro", "stasis": "fact", "context": "both"},
        {"label": "narrow targeted tax is workable", "claim": "A 1-2% annual tax on assets above £10 million targets only a tiny minority and would raise £20-30 billion.", "side": "pro", "stasis": "policy", "context": "UK"},
        {"label": "capital flight is overstated", "claim": "The vast majority of wealthy people do not relocate over modest tax changes; the 16,000-millionaire claim is debunked.", "side": "pro", "stasis": "fact", "context": "both"},
        {"label": "wealth is tied to place", "claim": "Wealth depends on local institutions, industries, and infrastructure, so relocating is costly and rare for the truly wealthy.", "side": "pro", "stasis": "fact", "context": "both"},
        {"label": "below revenue-maximizing rate", "claim": "Most OECD countries including the US and UK are below the revenue-maximizing tax rate, so higher rates would raise more revenue.", "side": "pro", "stasis": "fact", "context": "both"},
        {"label": "wealth taxes do work elsewhere", "claim": "Switzerland, Norway, and Spain demonstrate that well-designed annual wealth taxes are workable and raise revenue.", "side": "pro", "stasis": "fact", "context": "both"},
        {"label": "income overtaxed versus wealth", "claim": "Earned income is taxed heavily while wealth and capital gains are barely taxed, which is unfair and regressive.", "side": "pro", "stasis": "value", "context": "both"},
        {"label": "moral duty to contribute", "claim": "When millions live in poverty and public services collapse, the very wealthy have a moral obligation to contribute more.", "side": "pro", "stasis": "value", "context": "both"},
        {"label": "negligible loss to billionaires", "claim": "Even substantial wealth taxes leave billionaires extremely rich; the personal cost to them is negligible.", "side": "pro", "stasis": "value", "context": "both"},
        {"label": "fund public services and NHS", "claim": "Wealth tax revenue is needed to restore the NHS, public services, infrastructure, and to lift children out of poverty.", "side": "pro", "stasis": "policy", "context": "both"},
        {"label": "halt runaway concentration", "claim": "Without taxing top wealth, the rich will out-compete the middle class and own everything within a generation.", "side": "pro", "stasis": "policy", "context": "UK"},
        {"label": "immobile assets are taxable", "claim": "Land and major property holdings cannot be moved abroad, so an annual wealth tax on them is enforceable.", "side": "pro", "stasis": "fact", "context": "UK"},
        {"label": "austerity has failed", "claim": "Fourteen years of austerity have worsened services and infrastructure without delivering promised improvements; a new approach is needed.", "side": "pro", "stasis": "fact", "context": "UK"},
        {"label": "inheritance untaxed unfairness", "claim": "Large inheritors and aristocratic fortunes pay almost nothing as a percentage of lifetime wealth, making the system regressive.", "side": "pro", "stasis": "fact", "context": "UK"},
        {"label": "vested-interest critique", "claim": "Wealth-tax opponents (politicians, commentators, economists) often have direct financial interests undermining their objectivity.", "side": "pro", "stasis": "value", "context": "UK"},
        {"label": "social contract collapsing", "claim": "Allowing the wealthy to opt out of taxation collapses the post-war social contract and shifts burdens onto the immobile middle and poor.", "side": "pro", "stasis": "value", "context": "both"},
        {"label": "wealth-flight rhetoric is deflection", "claim": "The 'they will leave' objection is a recurring deflection raised only when taxing the rich, while austerity is readily imposed on the poor.", "side": "pro", "stasis": "value", "context": "UK"},
        {"label": "anti-woke distraction", "claim": "Culture-war and anti-woke rhetoric functions to distract from and protect concentrated wealth.", "side": "pro", "stasis": "value", "context": "UK"},
        {"label": "housing requires taxing wealth", "claim": "Housing unaffordability is driven by wealth concentration; building more homes alone cannot solve it without taxing top wealth.", "side": "pro", "stasis": "policy", "context": "UK"},
        {"label": "wealth as system health", "claim": "Wealth functions like calories in a body; concentration is a systemic health problem, not a left-right ideological issue.", "side": "pro", "stasis": "definition", "context": "both"},
        {"label": "inequality threatens democracy", "claim": "Curbing concentrated wealth is essential to preserving democratic institutions and political stability.", "side": "pro", "stasis": "value", "context": "both"},
    ],
    "shared": [
        {"label": "design matters for workability", "claim": "The specific design and threshold of any wealth tax critically determines whether it works.", "stasis": "procedure", "context": "both"},
        {"label": "current system has problems", "claim": "The current tax system and economy are not functioning well and need reform.", "stasis": "fact", "context": "both"},
        {"label": "fair share principle", "claim": "Everyone should pay their fair share of taxation, though sides disagree on what fair means.", "stasis": "value", "context": "both"},
        {"label": "close avoidance loopholes", "claim": "Tax avoidance loopholes, including trust-based inheritance avoidance and the borrow-against-gains gap, should be closed.", "stasis": "policy", "context": "both"},
        {"label": "some wealthy do leave", "claim": "Some wealthy individuals do relocate in response to tax changes, even if the magnitude is disputed.", "stasis": "fact", "context": "both"},
    ]
}

# Second prompt output — provenance
with open(DATA / "claim_provenance.json") as f:
    provenance = json.load(f)["positions"]

prov_by_label = {p["label"].strip().lower(): p for p in provenance}

def enrich(entry):
    label_key = entry["label"].strip().lower()
    prov = prov_by_label.get(label_key)
    if prov is None:
        print(f"  [WARN] no provenance for: {entry['label']!r}")
        entry["source_indices"] = []
        entry["source_debates"] = []
        entry["example_quotes"] = []
        entry["frequency"] = 0
    else:
        indices = prov["source_indices"]
        entry["source_indices"] = indices
        entry["frequency"] = len(indices)
        entry["example_quotes"] = prov["example_quotes"]

        # Build debate objects from claims_index using source_indices
        seen = {}
        for idx in indices:
            if idx < 1 or idx > len(claims_index):
                continue
            claim = claims_index[idx - 1]
            title = claim.get("debate", "")
            if title and title not in seen:
                seen[title] = {
                    "title": title,
                    "url": claim.get("url", ""),
                    "context": claim.get("context", ""),
                }
        entry["source_debates"] = list(seen.values())
    return entry

merged = {
    "positions": [enrich(p) for p in FIRST_OUTPUT["positions"]],
    "shared":    [enrich(p) for p in FIRST_OUTPUT["shared"]],
}

with open(DATA / "claim_positions.json", "w") as f:
    json.dump(merged, f, indent=2, ensure_ascii=False)

print("\nSummary:")
for section in ("positions", "shared"):
    for p in merged[section]:
        print(f"  [{section}] {p['label']!r}: freq={p['frequency']}, debates={len(p['source_debates'])}, quotes={len(p['example_quotes'])}")

print("\nDone.")
