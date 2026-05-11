# Argumentative Unit Detection Prompt

Use this prompt to split a long transcript into coherent **argumentative units** before skeletonization.

---

You are identifying argumentative units in a transcript for later skeletonization.

Your task is **not** to analyze the argument in depth.

Your task is to divide the transcript into coherent argumentative units.

An argumentative unit is a stretch of text where one coherent argumentative function is taking place.

Typical cases include:

- a substantive claim or position is advanced
- a direct response or counterargument is made
- a distinct point of stasis emerges
- a new policy mechanism or example is introduced in support of a position
- an audience or moderator intervention introduces a genuinely new dispute, question at issue, or line of challenge

Do **not** segment by equal length.
Segment by **argumentative coherence**.

## Rules

1. Each unit should contain one main argumentative function.
2. If a speaker shifts to a new dispute, start a new unit.
3. If the text is mostly procedural, introductory, corrupted, or non-substantive, mark it as non-argumentative.
4. Treat audience questions and moderator interventions by the same rule as everything else:
   - if they introduce a genuinely new argumentative issue, make them a separate unit
   - if they merely restate, clarify, or administratively manage an existing issue, keep them with the surrounding unit or mark them non-argumentative
5. Keep units large enough to preserve context, but small enough that one core dispute is visible.
6. Do not infer detailed claims yet. Just identify the unit boundaries and what kind of unit it is.
7. If a section contains clear transcription corruption, mixed-language OCR noise, or non-recoverable fragments, do not infer argument structure from it. Mark it low reliability.

## Common signals of a new unit

- explicit disagreement
  - “that’s not true”
  - “I disagree”
  - “that’s not apples with apples”
- a new question at issue
- a shift from moral fairness to economic mechanism
- a shift from claim to implementation or design
- a new audience intervention
- moderator reframing

## Output

Return YAML only in this schema:

```yaml
units:
  - unit_id: "u1"
    start_excerpt: ""
    end_excerpt: ""
    start_line: null
    end_line: null
    speakers:
      - ""
    unit_type: "opening_position | counterargument | rebuttal | clarification | audience_question | moderator_frame | non_argumentative | mixed"
    main_issue: ""
    usable_for_skeletonisation: true
    reliability: "high | medium | low"
    reason_if_low_or_false: ""
```

## Goal

Produce a segmentation that would make later skeletonization easier and cleaner.
