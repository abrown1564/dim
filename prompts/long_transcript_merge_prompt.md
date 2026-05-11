# Long Transcript Merge Prompt

Use this prompt after multiple argumentative units have already been skeletonized.

---

You are merging local skeletons from a long multi-party event into one discourse skeleton.

Your job is to:

- identify the major recurring points of stasis
- merge duplicate claims
- keep audience questions separate from panel positions where useful
- note where no consensus was reached
- preserve disagreement structure

## Rules

1. Do not invent agreement.
2. Do not collapse distinct disputes into one if they differ in stasis type.
3. Merge repeated claims only if they are substantively the same.
4. Keep facts-to-verify atomic.
5. Distinguish panel positions from moderator framing.
6. Preserve uncertainty when the unit-level skeletons are themselves low-reliability.
7. `common_ground_identified` must list every proposition that all speakers implicitly or explicitly accept — even if their overall positions differ. For monologic content, list premises the speaker treats as uncontested or concedes to opponents. Never return an empty list unless the transcript contains genuinely zero shared premises.
8. YAML values for `agreement_reached`, `consensus_reached`, `common_goal_agreed` must be quoted strings — write `"yes"`, `"no"`, or `"partial"`, never bare `yes`/`no` (which YAML parses as booleans).

## Output

Return YAML only in this schema:

```yaml
source_summary:
  discourse_mode: "monologic | dialogic | multi_party"
  overall_topic: ""
  agreement_reached: "yes | no | partial"
  consensus_reached: "yes | no | partial"
  common_goal_agreed: "yes | no | partial"
  common_ground_identified:
    - ""
participants:
  - label: ""
    role: "advocate | opponent | moderator | mixed | unclear"
    position_summary: ""
major_stasis_points:
  - stasis_type: "fact | definition | quality | procedure | mixed"
    question_at_issue: ""
    claims:
      - ""
    antitheses:
      - ""
    warrants:
      - ""
    status: "resolved | unresolved | partial_convergence"
facts_to_verify:
  - ""
assumptions_to_test:
  - ""
terms_to_define:
  - ""
meta_comment: ""
```

## Goal

Turn local unit skeletons into one stable discourse skeleton that can support:

- manual review
- claim-morpheme mapping
- later rhetorical attachment
- later discourse-profile generation

