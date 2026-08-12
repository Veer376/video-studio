---
name: produce-omni-story
description: "Plan, prompt, generate, review, repair, and render Gemini Omni Flash stories that use the video-project story-directory structure. Use for end-to-end story production or when continuing a story by whole story, part, or clip. Do not use for isolated prompt-only requests, still-image character design, or unrelated video models."
---

# Produce Omni Story

Orchestrate the complete story workflow without duplicating model-specific prompt knowledge.

## Required context

1. Locate the project root and read `README.md` and `AGENTS.md` completely.
2. Select the story under `stories/<story-slug>/` and read its `story.md`, `characters.json`, and `scenes.json` completely before changing or generating clips.
3. For a new story, follow [references/artifact-contracts.md](references/artifact-contracts.md) to initialize its files and directories.

## Working scope

If the user has not specified the working scope, ask once whether to work on:

- the complete story;
- one part; or
- one clip.

Use the chosen scope for the current task until the user changes it. Do not persist it in story files; ask again in a later task if the scope is unavailable. A batch scope permits batch planning and generation, but continuity-dependent clips still pass review in order.

## Phase routing

- For story design or revision, read [references/story-planning.md](references/story-planning.md).
- For an approved clip or part, read [references/scene-production.md](references/scene-production.md).
- After every generated or replaced clip, read [references/clip-review.md](references/clip-review.md).
- Render with the project renderer only after the requested canonical clips exist and have been reviewed.

## Hard boundaries

- Invoke `omni-flash-prompt-writer` independently for every Omni prompt, revision, or prompt diagnosis. Do not reproduce or guess its model rules.
- `story.md` owns story intent. `scenes.json` owns final authoring prompts. `characters.json` owns recurring-character reference paths.
- Before drafting or revising any part, reread the selected `story.md` creative contract and story-writing instructions.
- Use project-relative paths. Reuse project-level assets; do not copy them into every story.
- Preserve one canonical MP4 per scene. Replace it only through the bounded repair policy or explicit user authorization, and only after the replacement passes validation and review.
- A successful generation or playable file is not an accepted scene.
- Inspect a predecessor's exact final frame before generating any clip that uses it for continuity.
- A `needs_fix` decision permits at most two diagnosed repair retries for that scene. Log and review every attempt; if the second retry still returns `needs_fix`, stop and ask the user before any further generation.
- Do not claim dialogue or audio correctness from still frames.

## Completion

Complete only the requested scope. Report the story or scene paths, generation results, review decisions, accepted limitations, and any continuity repair required by the next clip.
