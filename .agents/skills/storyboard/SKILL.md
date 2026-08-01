---
name: storyboard
description: DEPRECATED. This skill has been split into two focused skills. Use split-script followed by design-visuals instead.
---

# Storyboard Skill — Deprecated

> [!WARNING]
> This skill has been **split into two separate, focused skills** for better quality and reliability. Do not use this skill directly.

## Migration

Replace any use of `storyboard` with this two-step sequence:

| Step | Skill | Responsibility |
|---|---|---|
| 1 | `split-script` | Divides the narration prose into scenes at natural boundaries. Writes the lean `scenes.json` skeleton (text, word_range only). |
| 2 | `design-visuals` | Reads the skeleton, builds character/prop visual identity sheets from the story context, and fills in `image_prompt` for every scene with cinematically-consistent, character-accurate descriptions. |

## Why the Split?

Combining script splitting (a logical/mathematical task) with visual prompt design (a creative task) in a single pass caused two systematic failures:

1. **Lazy character descriptions:** Under cognitive load, the model wrote `"the same boy"` instead of repeating the full visual sheet — breaking image-to-image consistency since the image model is stateless.
2. **Redundant and noisy fields:** The monolithic skill added `narration`, `subtitle`, `audio_path`, `duration_seconds`, `motion`, `transition`, and `voice_direction` fields that are either duplicates of `text` or belong to the render pipeline.

By separating the two concerns, each skill can focus entirely on its single responsibility and produce higher quality output.

## Status Transitions

- After `split-script` runs: `session.status = "split_complete"`
- After `design-visuals` runs: `session.status = "storyboard_complete"`

The `voice` skill activates on `storyboard_complete` — same as before.
