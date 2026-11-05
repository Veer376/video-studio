# Generated-video workflow

Read `README.md`, `.agents/skills/produce-story/SKILL.md`, and the selected production's authored files before acting. `story.md` owns creative intent; registries own recurring references; `scenes.json` owns executable prompts/inputs; `reviews/` owns active-clip decisions.

Before drafting, revising, or diagnosing any Omni prompt, read `.agents/skills/compile-omni-scene/SKILL.md` completely and apply it independently to that scene. If it is unavailable, stop prompt work rather than guessing model rules. Model-specific instructions belong to that skill, not the story brief.

Generate and review scenes sequentially through the project runner. Inspect the predecessor's exact final frame when chaining continuity. Reuse studio-level assets, keep project handles in authored prompts, and resolve ordered media references at request time. A playable clip is not an accepted clip: follow the clip-review evidence gate, preserve hash-bound findings/history, and render only accepted active clips. Diagnose rejected clips before replacement; retain archive/restore state and stop when the configured attempt limit is reached.

Generation can incur provider charges. Keep real productions in ignored working directories and back up runtime media/reviews separately. Image-story production belongs to the sibling pipeline and its own agent instructions.
