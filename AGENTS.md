# Video Pipeline Instructions

## Required workflow

- Use the project-local `produce-story` skill for story planning, scene production, clip review, repair, and final rendering in this repository.
- **Prompt production**: Before drafting, revising, or diagnosing any Gemini Omni Flash prompt even a rough draft — open and read `.agents/skills/compile-omni-scene/SKILL.md` in full. Apply it independently to every prompt.
- Treat prompt creation as an isolated model-specific pass. Use the selected story brief, scene facts, assets, and inspected continuity evidence as content inputs, but derive prompt structure, capability assumptions, and diagnostic rules only from the freshly read skill. Never rely on remembered skill content, earlier chat advice about Omni, or an old prompt's pattern.
- If `.agents/skills/compile-omni-scene/SKILL.md` cannot be opened and read completely, stop prompt work and report the blocker. Never guess or create a fallback prompt.

## Required context and ownership

- Before starting, read `README.md` and the story's files (`story.md` for rules/briefs—do not generalize, `characters.json` for character refs, `scenes.json` for prompts/inputs, `reviews/<scene-id>.json` for reviews).
- If scope is unspecified, ask once whether to work on the complete story, one part, or one clip, and retain that scope until changed.

## Hard production rules

- Process scenes sequentially. Draft, generate, and review scene N before drafting scene N+1 in `scenes.json`.
- Use project-relative paths. Reuse project-level assets instead of copying them into every story.
- Register only recurring characters whose visual identity must remain consistent. Describe one-off figures and flexible story elements directly in scene prompts.
- Keep project `@handles` in `scenes.json`; resolve them to ordered Gemini image references only at request time. Do not store an `extended_prompt`.
- When adjacent scenes continue the same physical moment, inspect the predecessor's exact final frame and use `reference_scene_id` when that frame should anchor the next scene's opening. Skip literal frame chaining when the transition intentionally changes time, place, perspective, or composition.

## Temp
- There is no narration verification script in the project, skip narration verification for now.
- For the image creation for characters or for any other use-case, use `flow` skill.
