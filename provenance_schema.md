# Provenance Schema
## For `taxonomy.json` and `debate_terminology.json`

**Purpose:** Define a shared provenance structure for concepts, fallacies, coined terms, and debate-theory entries so the project can distinguish:

- where a term originally comes from
- what sources support DIM's current definition
- whether a term is established, adapted, or coined inside DIM

This file defines the schema only. It does **not** mean every entry has been populated yet.

---

## Design goals

The provenance layer should let DIM say, clearly:

1. **Who introduced this term or concept?**
2. **What is the original work or tradition?**
3. **What sources support the definition DIM is using now?**
4. **Is this an established term, an adapted use, or a DIM-coined label?**
5. **If DIM coined it, what older literature or neighboring concepts is it building from?**

This matters especially because the taxonomy now mixes:

- classical logical and rhetorical terms
- modern argumentation-theory terms
- NLP/communication-theory concepts
- DIM-coined labels

---

## Recommended fields

### Top-level provenance fields

These fields should be available on entries in both `taxonomy.json` and `debate_terminology.json`.

```json
{
  "provenance": "established",
  "original_source": {
    "author": "Aristotle",
    "title": "Sophistical Refutations",
    "year": "c. 350 BCE",
    "tradition": "Ancient Greek",
    "url": "https://example.org",
    "notes": "Earliest relevant named treatment or canonical source."
  },
  "sources": [
    {
      "author": "Frans H. van Eemeren",
      "title": "The Pragma-Dialectical Approach to the Fallacies Revisited",
      "year": 2023,
      "type": "secondary",
      "url": "https://link.springer.com/article/10.1007/s10503-023-09605-w",
      "notes": "Useful modern restatement."
    }
  ],
  "dim_usage_note": "DIM uses this term in a narrower debate-analytic sense than some broader philosophical treatments."
}
```

---

## Field meanings

### `provenance`

Required.

Allowed values:

- `established`
- `adapted`
- `coined`

Meaning:

- `established`: DIM is using a term that already exists in recognizable prior literature
- `adapted`: DIM is borrowing an established term but using it in a narrowed, extended, or recontextualized way
- `coined`: DIM is naming a pattern that is not yet clearly formalized under that label in prior literature

### `original_source`

Recommended for all entries except where genuinely unknown.

Purpose:

- identifies the earliest or most canonical source for the term, concept, or distinction

Recommended subfields:

- `author`
- `title`
- `year`
- `tradition`
- `url`
- `notes`

This should usually point to **one** source:

- the canonical origin
- or the earliest source DIM is confidently using as origin

If origin is diffuse or uncertain, `notes` should say so.

### `sources`

Recommended for all entries.

Purpose:

- records the supporting literature behind DIM's current definition or use

This should be an array because one source is rarely enough.

Recommended subfields per source:

- `author`
- `title`
- `year`
- `type`
- `url`
- `notes`

Recommended values for `type`:

- `primary`
- `secondary`
- `survey`
- `reference`
- `adjacent`
- `dim_internal`

### `dim_usage_note`

Optional but strongly recommended.

Purpose:

- explains how DIM is using the term if that use differs from ordinary or historical usage

This is especially important for:

- adapted terms
- broad concepts narrowed into debate-analysis use
- coined entries built from neighboring literature

---

## Minimal example patterns

### 1. Established term

```json
{
  "id": "straw_man",
  "name": "Straw Man",
  "provenance": "established",
  "original_source": {
    "author": "Douglas Walton",
    "title": "The Straw Man Fallacy",
    "year": 1996,
    "tradition": "Modern Argumentation Theory",
    "url": "https://books.google.com/",
    "notes": "Use a canonical modern source if ancient origin is diffuse."
  },
  "sources": [
    {
      "author": "Douglas Walton",
      "title": "The Straw Man Fallacy",
      "year": 1996,
      "type": "primary",
      "url": "https://books.google.com/",
      "notes": "Core monograph treatment."
    },
    {
      "author": "Frans H. van Eemeren",
      "title": "The Pragma-Dialectical Approach to the Fallacies Revisited",
      "year": 2023,
      "type": "secondary",
      "url": "https://link.springer.com/article/10.1007/s10503-023-09605-w",
      "notes": "Useful rule-violation framing."
    }
  ]
}
```

### 2. Adapted term

```json
{
  "id": "dialectic",
  "name": "Dialectic",
  "provenance": "adapted",
  "original_source": {
    "author": "Plato / Aristotle",
    "title": "Classical Greek dialectical tradition",
    "year": "Ancient",
    "tradition": "Ancient Greek",
    "url": null,
    "notes": "Origin is distributed across major classical sources."
  },
  "sources": [
    {
      "author": "Frans H. van Eemeren and Rob Grootendorst",
      "title": "A Systematic Theory of Argumentation",
      "year": 2004,
      "type": "secondary",
      "url": "https://www.cambridge.org/",
      "notes": "Modern formalization relevant to DIM."
    }
  ],
  "dim_usage_note": "DIM uses dialectic as the positive pole of a practical quality axis rather than only as a historical philosophical method."
}
```

### 3. Coined DIM term

```json
{
  "id": "performed_empiricism",
  "name": "Performed Empiricism",
  "provenance": "coined",
  "original_source": {
    "author": "Discourse Integrity Map",
    "title": "DIM taxonomy development",
    "year": 2026,
    "tradition": "DIM internal",
    "url": null,
    "notes": "Coined during taxonomy development; not claimed as an established term in prior literature."
  },
  "sources": [
    {
      "author": "Discourse Integrity Map",
      "title": "DIM taxonomy development notes",
      "year": 2026,
      "type": "dim_internal",
      "url": null,
      "notes": "Internal naming origin."
    },
    {
      "author": "Relevant adjacent literature",
      "title": "Source to be added",
      "year": null,
      "type": "adjacent",
      "url": null,
      "notes": "Should point to neighboring concepts once identified."
    }
  ],
  "dim_usage_note": "Coined as a label for the staged performance of evidential seriousness without corresponding evidential rigor."
}
```

---

## Practical population strategy

Do **not** try to fully populate provenance for every entry at once.

Recommended order:

1. High-priority taxonomy entries used in the MVP corpus
2. Core conceptual entries such as `dialectic`, `eristic`, `good_faith`, `pragma_dialectics`
3. All DIM-coined entries
4. Debate terminology reference entries
5. Long-tail taxonomy entries

---

## Recommendation for implementation

### First pass

Add these fields to `taxonomy.json` first:

- `provenance`
- `original_source`
- `sources`
- `dim_usage_note`

Populate them first for:

- `dialectic`
- `eristic`
- `pragma_dialectics`
- `good_faith`
- `straw_man`
- `ad_hominem`
- `cherry_picking`
- `gish_gallop`
- all `coined` entries

### Second pass

Mirror the same structure into `debate_terminology.json`, especially for:

- `dialectic`
- `eristic`
- `quaestio`
- `paideia`
- `decorum`
- `turn_taking`
- `responsiveness`

---

## Why this matters for DIM

This schema helps DIM avoid three problems:

1. **False novelty**
   DIM should not accidentally present established concepts as if it invented them.

2. **False authority**
   DIM should not imply that coined labels have ancient or canonical standing when they do not.

3. **Theoretical vagueness**
   DIM should be able to say exactly which tradition, theory, or paper supports a given category.

The provenance layer is therefore not just documentation. It is part of the project’s epistemic credibility.
