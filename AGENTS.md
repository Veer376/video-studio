# Project instructions

## Required workflow

- Use the project-local `produce-omni-story` skill for story planning, scene production, clip review, repair, and final rendering in this repository.
- **Non-negotiable prompt gate:** Before drafting, revising, or diagnosing any Gemini Omni Flash prompt—even a rough draft—open and read the current shared `omni-flash-prompt-writer/SKILL.md` completely in that task. Then apply it independently to every prompt.
- Treat prompt creation as an isolated model-specific pass. Use the selected story brief, scene facts, assets, and inspected continuity evidence as content inputs, but derive prompt structure, capability assumptions, and diagnostic rules only from the freshly read skill. Never rely on remembered skill content, earlier chat advice about Omni, or an old prompt's pattern.
- If `omni-flash-prompt-writer/SKILL.md` cannot be opened and read completely, stop prompt work and report the blocker. Never guess or create a fallback prompt.
- Do not use `omni-flash-prompt-writer` for still-image character design or API implementation.
- This project supports Gemini Omni Flash only. Do not generalize its contracts to unrelated video models.

## Required context and ownership

- Before working on a story, read `README.md` plus the selected story's `story.md`, `characters.json`, and `scenes.json` completely.
- `story.md` owns story-specific creative rules and clip briefs. Do not turn one story's pacing, palette, language, or genre into a project-wide default.
- `characters.json` owns recurring-character references. `scenes.json` owns final authoring prompts and generation inputs. `reviews/<scene-id>.json` owns review decisions.
- If the user did not choose a scope, ask once whether to work on the complete story, one part, or one clip; retain that scope until changed.

## Hard production rules

- Use project-relative paths. Reuse project-level assets instead of copying them into every story.
- Register only recurring characters whose visual identity must remain consistent. Describe one-off figures and flexible story elements directly in scene prompts.
- Keep project `@handles` in `scenes.json`; resolve them to ordered Gemini image references only at request time. Do not store an `extended_prompt`.
- Use `reference_scene_id` only when a predecessor's final frame must be the literal opening anchor. Inspect that exact frame before producing the dependent scene.
- A successful generation or playable MP4 is not an accepted scene. Validate media streams, review observable evidence, and persist the review decision.
- Do not claim dialogue or audio correctness from still frames.
- When review returns `needs_fix`, diagnose and retry autonomously no more than three times for that scene. Append every attempt, diagnosis, and repair action to its review JSON. If the third retry still returns `needs_fix`, stop and ask the user before generating again.
