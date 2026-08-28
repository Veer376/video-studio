# Video Studio

An agent-assisted workspace for creating story videos with Gemini Omni Flash. It turns a story idea into short generated scenes, reviews each active clip, and renders the accepted sequence with FFmpeg.

The repository also holds reusable visual assets, standalone execution prompts, channel resources, and small command interfaces around the production scripts.

## How it works

```text
idea or script
    → story plan and recurring assets
    → scene prompts and references
    → active scene videos
    → evidence-based review and repair
    → final render and publishing assets
```

Gemini Omni Flash prompt creation is delegated to the project-local `compile-omni-scene` skill. It preserves one provider-neutral authoring prompt while the Flow and Gemini API adapters apply their own request configuration. The `produce-story` skill coordinates planning, generation, review, repair, and rendering without duplicating model-specific prompting rules.

## Project structure

```text
.agents/skills/       project-local agent workflows and utilities
app/                  desktop and terminal command interfaces
assets/               reusable characters, locations, and vehicles
voices.json           reusable off-screen narration voice profiles
prompts/              standalone prompts for optional or ad-hoc workflows
scripts/              maintained generation, review, and rendering utilities
projects/             canonical production projects
stories/              existing legacy production projects
temp/                 non-canonical scratch files and test artifacts
kahanikachakkar/       Kahani Ka Chakkar channel resources
kathamind/             Katha Mind channel resources
youtube/               shared publishing-asset conventions
AGENTS.md              repository-wide agent rules
GEMINI.md              Gemini entry point to the repository rules
```

Reusable assets stay at studio level. Files needed only by one production project stay inside that project. Temporary experiments are not production state.

Off-screen recurring narrators use `@narration-*` handles registered in
project-root `voices.json`. Scene prompts place the handle directly at the
voiceover source (for example, `A single off-screen @narration-kathamind
voiceover...`). Narration handles are audio-only and do not belong in the
scene `subjects` array.

## Production project structure

Each new directory under `projects/<project-slug>/` may contain:

```text
story.md         source constraints, story, direction, and scene briefs
characters.json recurring character handles and reference images
scenes.json     final scene prompts and generation inputs
assets/         project-specific visual assets
temp/           continuity frames, contact sheets, and other review evidence
reviews/        current scene decisions and preserved review history
videos/         active scene clips and archived rejected versions
output/         final renders and delivery assets
```

The core sources of truth are:

- `story.md` for creative intent and progression.
- `characters.json` for recurring, consistency-critical references.
- `scenes.json` for executable scene inputs.
- `reviews/<scene-id>.json` for review and selection state.
- `videos/` for accepted active clips and archived rejected versions.

## Main tools

- `produce-story`: runs the story-production workflow at whole-story or scene scope.
- `compile-omni-scene`: translates approved scene direction into an Omni authoring prompt and validates provider capability.
- `create-prompt`: clarifies and saves one standalone prompt without executing it.
- `scripts/generate_scenes.py`: generates active clips and archives rejected versions before replacement.
- `scripts/render_video.py`: joins accepted active scene clips into a final video.
- `scripts/render_text.py`, `scripts/apply_watermark.py`, and `scripts/add_loop.py`: optional post-production passes.
- `app/`: provides local command interfaces over maintained project utilities.

Operational rules, retry limits, continuity handling, and review decisions are defined in `AGENTS.md` and the project-local skills.

## Basic usage

Optional configuration and routing diagnostics without consuming quota:

```bash
python3 scripts/generate_scenes.py \
  --config projects/<project-slug>/scenes.json \
  --dry-run
```

Generate scenes for a story:

```bash
python3 scripts/generate_scenes.py \
  --config projects/<project-slug>/scenes.json
```

Render its accepted active clips:

```bash
python3 scripts/render_video.py \
  --config projects/<project-slug>/scenes.json \
  --output projects/<project-slug>/output/final-video.mp4
```

Generation uses Google Cloud Application Default Credentials when available, otherwise `GEMINI_API_KEY`. Credentials must not be copied into the repository.
