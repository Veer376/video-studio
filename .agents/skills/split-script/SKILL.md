---
name: split-script
description: Divide an approved narration script into lossless semantic visual beats for one-image-per-scene production. Use when script.md exists and scenes.json is missing, when a word-count split creates overloaded or repetitive images, or when the user requests a semantic re-split. Preserves narration exactly, writes only the skeleton scene manifest, and validates it deterministically.
---

# Split Script

Treat each scene as an image-hold interval: one contiguous narration span that one temporally coherent still can represent truthfully. Word-timed subtitles and TTS units are downstream concerns.

Do not write image prompts, choose a visual design, rewrite narration, or manufacture a target scene count.

## Inputs

Read:

1. `library/<project_name>/session.json`
2. `library/<project_name>/script.md`
3. existing `scenes.json` only when the user requests a re-split

Use only the narration after the first `---`. Remove bracketed performance directions from the scene text. Preserve all spoken words and punctuation. Preserve `>` quote markers for the current renderer; repeat `> ` at the beginning of a continuation scene when a marked quote spans scenes.

## Workflow

1. Read [references/semantic-boundaries.md](references/semantic-boundaries.md).
2. **Pass 1 — Candidate boundaries:** walk the entire narration and mark every natural point where the required visible situation may change. Do not count toward a scene quota.
3. **Pass 2 — Boundary ledger:** for every candidate span, record internally its earliest moment, latest moment, grounded image, reveal level, and estimated hold. Audit the complete sequence in this order:
   1. split temporally incompatible moments; attach brief transitions to their endpoint
   2. split before an image would expose a subject, object, or result earlier than the narration
   3. merge dialogue turns that share one tableau unless an action, object, power state, or decisive reveal changes
   4. review estimated holds above roughly 15 seconds for a distinct narration-grounded shot purpose
   5. merge abstract or audience-facing spans whose separate image would be generic or repeat the established consequence

   For every surviving cut, compare the images on both sides. Remove the cut when they are substantially the same; retain it only when both descriptions are materially distinct and narration-grounded.
4. Read [references/manifest-contract.md](references/manifest-contract.md) and write the skeleton `scenes.json`.
5. Run:

```bash
python3 .agents/skills/split-script/scripts/validate_split.py --project-dir library/<project_name>
```

6. Correct every failure before setting `session.status` to `split_complete`.
7. Report a compact decision table with scene ID, word count, estimated hold when available, dominant visible state, and the reason its boundary begins. Do not persist this reasoning in `scenes.json`.

## Re-splitting

If `scenes.json` contains prompts, images, timings, or other production fields, do not overwrite it immediately. First present the proposed boundary changes and identify invalidated downstream scenes. Obtain confirmation before replacing the manifest.

Preserve an existing scene ID only when its exact narration span and visual meaning remain unchanged. A changed span must not inherit an old image by filename.

## Completion Standard

- The validator passes.
- Every scene has one dominant depictable visual state.
- No scene combines mutually exclusive sequential moments.
- No adjacent scenes repeat one unchanged visual state without a semantic reason.
- Every boundary earns a materially different, narration-grounded image; discourse structure alone does not earn a cut.
- The sequence preserves reveals, causality, continuity, and the complete narration.
