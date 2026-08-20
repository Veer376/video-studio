# Video Pipeline Instructions

## Required workflow

- Use the project-local `produce-story` skill for story planning, scene production, clip review, repair, and final rendering in this repository.
- **Prompt production (subagent available)**: Use the subagent to generate the Omni Flash prompt from the refined scene. Give it a detailed description of the scene and what it depicts. When fixing a scene prompt, use the same subagent that produced the original prompt. Ask it to verify the contact sheet and notes, then produce a corrected prompt following `.agents/skills/compile-omni-scene/SKILL.md`.
- **Prompt production (no subagent)**: Before drafting, revising, or diagnosing any Gemini Omni Flash prompt — even a rough draft — open and read `.agents/skills/compile-omni-scene/SKILL.md` in full. Apply it independently to every prompt.
- Treat prompt creation as an isolated model-specific pass. Use the selected story brief, scene facts, assets, and inspected continuity evidence as content inputs, but derive prompt structure, capability assumptions, and diagnostic rules only from the freshly read skill. Never rely on remembered skill content, earlier chat advice about Omni, or an old prompt's pattern.
- If `.agents/skills/compile-omni-scene/SKILL.md` cannot be opened and read completely, stop prompt work and report the blocker. Never guess or create a fallback prompt.
- This project supports Gemini Omni Flash only. Do not generalize its contracts to unrelated video models.

## Required context and ownership

- Before working on a story, read `README.md` plus the selected story's `story.md`, `characters.json`, and `scenes.json` completely.
- `story.md` owns story-specific creative rules and clip briefs. Do not turn one story's pacing, palette, language, or genre into a project-wide default.
- `characters.json` owns recurring-character references. `scenes.json` owns final authoring prompts and generation inputs. `reviews/<scene-id>.json` owns review decisions.
- If the user did not choose a scope, ask once whether to work on the complete story, one part, or one clip; retain that scope until changed.

## Hard production rules

- Process scenes sequentially. Draft, generate, review, and promote scene N before drafting scene N+1.
- Use project-relative paths. Reuse project-level assets instead of copying them into every story.
- Register only recurring characters whose visual identity must remain consistent. Describe one-off figures and flexible story elements directly in scene prompts.
- Keep project `@handles` in `scenes.json`; resolve them to ordered Gemini image references only at request time. Do not store an `extended_prompt`.
- Use `reference_scene_id` only when a predecessor's final frame must be the literal opening anchor. Inspect that exact frame before producing the dependent scene.
- Generate every attempt under the selected story's `temp/partial/` directory. Promote only the reviewed selected attempt to the canonical `videos/` path; never generate or retry directly over a canonical clip.
- A successful generation or playable MP4 is not an accepted scene. Validate media streams, review observable evidence, and persist the review decision.
- Do not claim dialogue or audio correctness from still frames.
- When review returns `needs_fix`, diagnose and retry no more than two times for that scene, producing three total attempts. Append every attempt, diagnosis, repair action, and evidence path to its review JSON.
- If all three attempts remain `needs_fix`, stop in interactive work. In explicitly autonomous work, compare every media-valid attempt against the clip contract, select and record one `best_available` attempt, promote it, report its unresolved defects, and continue. Stop only when no media-valid candidate exists.


## Temp
- there is no narration verification script in the project, skip narration verification for now.
- if a subagent is used for scene fixes, ask it at the end of its work: if you think `.agents/skills/compile-omni-scene/SKILL.md` needs an update, write the proposed change to `subagent/fixes.md`.
- For the image creation for characters or for any other use, use /flow skill.
