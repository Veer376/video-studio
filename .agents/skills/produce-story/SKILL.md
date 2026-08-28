---
name: produce-story
description: "Plan, prompt, generate, review, repair, and render Gemini Omni Flash stories that use the Video Studio project structure. Use for end-to-end story production or when continuing a story by whole story, part, or scene. Do not use for isolated prompt-only requests, still-image character design, or unrelated video models."
---

# Produce Story

Orchestrate the complete story workflow without duplicating model-specific prompt knowledge.

## Required context

1. Locate the studio root and read `README.md` and `AGENTS.md` completely.
2. Select the production project under `projects/<project-slug>/`; existing projects under `stories/` remain valid. Read the studio-root `characters.json`, the selected project's `characters.json`, `story.md`, and `scenes.json` completely before changing or generating clips. Resolve any `@handle` from the project registry first, then the studio registry.
3. For a new project, initialize it through `scripts/project.py`, then follow [references/artifact-contracts.md](references/artifact-contracts.md).

## Working scope

If the user has not specified the working scope, ask once whether to work on:

- the complete story;
- one part; or
- one scene.

Use the chosen scope until changed. Working scope defines the target boundary, but scene production is strictly sequential: prompt, generate, and review one scene at a time.

In autonomous execution, advance through the sequential scene pipeline to completion without pausing for routine confirmations. In interactive execution, confirm after each scene.

## Phase routing

- For story design or revision, read [references/story-planning.md](references/story-planning.md).
- When a required recurring character is missing or incomplete, read [references/character-readiness.md](references/character-readiness.md).
- For an approved scene, read [references/scene-production.md](references/scene-production.md).
- After every generated or replaced scene, read [references/clip-review.md](references/clip-review.md).
- Render with the project renderer only after the requested active clips exist and have been accepted.

## Hard boundaries

- Invoke `compile-omni-scene` independently for every Omni prompt, revision, or prompt diagnosis. Do not reproduce or guess its model rules.
- `story.md` owns story intent. `scenes.json` owns final authoring prompts. The studio-root `characters.json` owns reusable characters; the selected project's `characters.json` owns project-specific characters and overrides.
- Before drafting or revising any part, reread the selected `story.md` creative contract and story-writing instructions.
- Use repository-relative paths. Reuse studio-level assets; do not copy them into every project.
- Generate through the project runner. The scene's `output_path` is its active video.
- A successful generation or playable file is not an accepted scene.
- Inspect a predecessor's exact final frame before generating any clip that uses it for continuity.
- After `needs_fix`, diagnose and revise before running the scene once more. If the replacement also needs fixing, stop and ask the user whether to restore an archived video or revise the scene manually.
- Do not claim dialogue or audio correctness from still frames.

## Completion

Complete only the requested scope. Report the project or scene paths, generation results, review decisions, accepted limitations, and any continuity repair required by the next scene.
