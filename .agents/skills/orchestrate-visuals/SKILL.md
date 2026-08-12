---
name: orchestrate-visuals
description: Create or revise narration-faithful visual direction for Story Video Maker scenes. Use after the image-story split stage, when registering or reusing recurring character identities, or when existing image prompts drift from scene text. Writes character mappings, concrete scene prompts, and continuity references without changing narration or scene boundaries.
---

# Orchestrate Visuals

Act as the story's cinematographer. Translate each narration scene into one clear, renderable image. Narrative truth outranks novelty.

Do not change narration, scene boundaries, or timing. Work only on character identity, prompt craft, framing, and continuity. Do not generate images; production owns generation.

## Inputs

Read before writing:

1. `library/<project_name>/session.json` for `visual.style`, `visual.aspect_ratio`, and `voice.language`
2. `library/<project_name>/scenes.json` for every scene and existing production state
3. `library/<project_name>/script.md` for the full arc, recurring subjects, setting, and props
4. project `research.md` only when identity or period claims require its evidence

For first-pass orchestration, expect `session.status: "split_complete"` and missing or null scene prompts. For revisions, preserve later status and valid production fields.

## Workflow

1. Read [references/character-assets.md](references/character-assets.md). Register recurring subjects, inspect reusable root assets, and choose reuse, adaptation, or new generation semantics.
2. Read [references/scene-direction.md](references/scene-direction.md). Build the continuity ledger and direct one narration-faithful still per scene.
3. Read [references/manifest-contract.md](references/manifest-contract.md). Apply the schema, run the fidelity gate, and write `scenes.json` safely.

On first-pass completion, update `session.status` from `split_complete` to `storyboard_complete`. On correction, preserve later status and identify which scene images require forced regeneration.

## Hard Boundaries

- Preserve every scene's `id`, `text`, boundaries, timings, and unrelated production fields.
- Keep `visual.style` only in top-level `visual_style`; never duplicate it in character or scene prompts.
- Use concrete visible language, supported historical details, backward-only compatible scene references, and exact required in-image text.
- Never write `reference_weight`; the active provider does not expose it.
- Keep all project-local character outputs under `assets/characters/`. Shared root assets are read-only.
