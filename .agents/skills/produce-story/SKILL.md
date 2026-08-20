---
name: produce-story
description: "Plan, prompt, generate, review, repair, and render Gemini Omni Flash stories that use the video-project story-directory structure. Use for end-to-end story production or when continuing a story by whole story, part, or clip. Do not use for isolated prompt-only requests, still-image character design, or unrelated video models."
---

# Produce Story

Orchestrate the complete story workflow without duplicating model-specific prompt knowledge.

## Required context

1. Locate the project root and read `README.md` and `AGENTS.md` completely.
2. Select the story under `stories/<story-slug>/` and read the project-root `characters.json` (global registry), the story's `characters.json` (story-specific additions), `story.md`, and `scenes.json` completely before changing or generating clips. Resolve any `@handle` by checking the story registry first, then the global registry.
3. For a new story, follow [references/artifact-contracts.md](references/artifact-contracts.md) to initialize its files and directories.

## Working scope

If the user has not specified the working scope, ask once whether to work on:

- the complete story;
- one part; or
- one clip.

Use the chosen scope until changed. Working scope defines the target boundary, but scene production is strictly sequential: prompt, generate, review, and promote one scene at a time.

In autonomous execution, advance through the sequential scene pipeline to completion without pausing for routine confirmations. In interactive execution, confirm after each scene. Record autonomous fallback selections in review JSON, not in `story.md`.

## Phase routing

- For story design or revision, read [references/story-planning.md](references/story-planning.md).
- When a required recurring character is missing or incomplete, read [references/character-readiness.md](references/character-readiness.md).
- For an approved clip or part, read [references/scene-production.md](references/scene-production.md).
- After every generated or replaced clip, read [references/clip-review.md](references/clip-review.md).
- Render with the project renderer only after the requested canonical clips exist and have been reviewed.

## Hard boundaries

- Invoke `compile-omni-scene` independently for every Omni prompt, revision, or prompt diagnosis. Do not reproduce or guess its model rules.
- `story.md` owns story intent. `scenes.json` owns final authoring prompts. The project-root `characters.json` owns reusable characters; the story-level `characters.json` owns story-specific characters and overrides.
- Before drafting or revising any part, reread the selected `story.md` creative contract and story-writing instructions.
- Use project-relative paths. Reuse project-level assets; do not copy them into every story.
- Preserve every generation as an attempt candidate under `temp/partial/`. Promote exactly one reviewed selected attempt to the canonical scene path; never generate or retry directly over a canonical clip.
- A successful generation or playable file is not an accepted scene.
- Inspect a predecessor's exact final frame before generating any clip that uses it for continuity.
- A `needs_fix` decision permits at most two diagnosed repair retries, producing three total attempts. Log and review every attempt. After the third failure, interactive execution stops; explicitly autonomous execution selects the best media-valid attempt as `best_available`, promotes it with unresolved defects recorded, and continues. Stop autonomous execution only when no media-valid attempt exists.
- Do not claim dialogue or audio correctness from still frames.

## Completion

Complete only the requested scope. Report the story or scene paths, generation results, review decisions, accepted limitations, and any continuity repair required by the next clip.
