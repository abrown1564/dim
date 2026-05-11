# Unit Skeletonization Prompt

Use this prompt on a **single argumentative unit** after segmentation.

---

You are skeletonizing one argumentative unit from a longer public discussion.

Extract only the **minimal faithful argumentative structure** of this unit.

Do not evaluate.
Do not detect fallacies.
Do not summarize rhetoric.
Do not force structure if the unit is mostly procedural or low-content.

Return:

- whether the unit contains substantive argument
- local point(s) of stasis
- speaker claims and antitheses
- warrants
- facts to verify
- assumptions to test
- terms to define

## Rules

1. Strip rhetoric and flourish; preserve only argumentative substance.
2. Keep claims atomic where possible.
3. Separate factual disputes from normative disputes.
4. If a speaker only reports or frames another position, mark that clearly.
5. If the unit has no meaningful argumentative content, say so.
6. Each fact to verify must be atomic. If an item needs “and”, split it.
7. If a warrant is unclear, use `null`.
8. Preserve only the minimal faithful form of the argument, not the broadest or most generic paraphrase.
9. Always populate `source_anchor` with the unit_id, line range, and a verbatim excerpt long enough to uniquely locate this unit in the original transcript. Do not paraphrase the excerpt.
10. Set `policy_stance` to the unit's net argumentative position on the core policy question (here: a wealth tax):
    - `pro` — unit argues in favour of a wealth tax
    - `anti` — unit argues against a wealth tax
    - `neutral` — purely informational, framing, or procedural with no evaluative stance
    - `mixed` — unit contains substantive arguments on both sides
11. YAML formatting — strictly follow these rules or the output will be rejected:
    - Never use `---` anywhere in your response. It is a YAML document separator and will break parsing.
    - All list items must be plain quoted strings. Never add parenthetical annotations after a string, e.g. write `- “wealth tax”` not `- “wealth tax” (meaning: tax on net assets)`.

## Output

Return YAML only in this schema:

```yaml
section_id: ""
usable_argument: true
section_summary: ""
policy_stance: "pro | anti | neutral | mixed"
source_anchor:
  unit_id: ""
  start_line: null
  end_line: null
  verbatim_excerpt: ""
local_stasis_points:
  - stasis_type: "fact | definition | quality | procedure | mixed"
    question_at_issue: ""
    speaker_claims:
      - speaker: ""
        claim: ""
        stance: "endorses | reports | rejects"
    antitheses:
      - speaker: ""
        claim: ""
    counterclaims:
      - ""
    warrants:
      - speaker: ""
        warrant: ""
    key_spans:
      - ""
facts_to_verify:
  - ""
assumptions_to_test:
  - ""
terms_to_define:
  - ""
```

## Goal

Produce a local skeleton that can later be merged into a larger discourse map without carrying over rhetorical noise.

