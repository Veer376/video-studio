# Manifest Contract

## Skeleton Schema

Write exactly:

```json
{
  "project_name": "<session project name>",
  "total_words": 42,
  "scene_count": 3,
  "scenes": [
    {
      "id": "scene-001",
      "text": "<exact contiguous narration span>"
    }
  ]
}
```

Do not add prompts, characters, image paths, references, timings, audio fields, motion, transitions, or reasoning during the initial split.

## Lossless Rules

- Scene texts form one ordered, contiguous partition of the narration body.
- Remove only bracketed performance directions and non-spoken document framing.
- Do not rewrite, summarize, correct, duplicate, omit, or reorder spoken prose or punctuation.
- Boundary whitespace may normalize to a single space.
- Repeated leading `> ` markers for quote continuation are control markers and do not count as duplicated prose.
- Preserve every quoted/unquoted transition. A scene may cross that transition only when the corresponding line break and `>` state remain explicit; never let a leading quote marker absorb later unquoted narration.
- `total_words` counts non-whitespace narration tokens after removing performance and quote-control markers.
- IDs are contiguous: `scene-001`, `scene-002`, and so on.

## Deterministic Gate

The validator checks schema, IDs, counts, minimum span size, quote-marker scope, absence of performance tags, and lossless reconstruction. It cannot judge visual meaning; apply the semantic completion standard in `SKILL.md` after it passes.

For an isolated proposal or fixture, specify paths directly:

```bash
python3 .agents/skills/split-script/scripts/validate_split.py \
  --script-file /path/to/script.md \
  --scenes-file /path/to/scenes.json
```
