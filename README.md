# Video Project

An agent-assisted workspace for creating story videos with Gemini Omni Flash. It turns a story idea into short generated scenes, reviews each candidate, keeps one canonical clip per scene, and renders the approved sequence with FFmpeg.

The repository also holds reusable visual assets, standalone execution prompts, channel resources, and small command interfaces around the production scripts.

## How it works

```text
idea or script
    → story plan and recurring assets
    → scene prompts and references
    → generated clip attempts
    → evidence-based review and selection
    → canonical scene videos
    → final render and publishing assets
```

Gemini Omni Flash prompt creation is delegated to the shared `omni-flash-prompt-writer` skill. The project-local `produce-story` skill coordinates planning, generation, review, repair, and rendering without duplicating model-specific prompting rules.

## Project structure

```text
.agents/skills/       project-local agent workflows and utilities
app/                  desktop and terminal command interfaces
assets/               reusable characters, locations, and vehicles
prompts/              standalone prompts for optional or ad-hoc workflows
scripts/              maintained generation, review, and rendering utilities
stories/              self-contained story projects and their production state
temp/                 non-canonical scratch files and test artifacts
kahanikachakkar/       Kahani Ka Chakkar channel resources
kathamind/             Katha Mind channel resources
youtube/               shared publishing-asset conventions
AGENTS.md              repository-wide agent rules
GEMINI.md              Gemini entry point to the repository rules
```

Reusable assets stay at project level. Files needed only by one story stay inside that story. Temporary experiments are not production state.

## Story structure

Each directory under `stories/<story-slug>/` may contain:

```text
story.md         creative direction, story parts, and scene briefs
characters.json recurring character handles and reference images
scenes.json     final scene prompts and generation inputs
assets/         story-specific visual assets
temp/partial/   generated attempt candidates
temp/           continuity frames, contact sheets, and other review evidence
reviews/        persisted scene decisions and attempt history
videos/         selected canonical scene clips
output/         final renders and delivery assets
```

The core sources of truth are:

- `story.md` for creative intent and progression.
- `characters.json` for recurring, consistency-critical references.
- `scenes.json` for executable scene inputs.
- `reviews/<scene-id>.json` for review and selection state.
- `videos/` for the canonical clips used by the renderer.

## Main tools

- `produce-story`: runs the story-production workflow at whole-story, part, or clip scope.
- `create-prompt`: clarifies and saves one standalone prompt without executing it.
- `scripts/generate_scenes.py`: generates candidates and promotes reviewed selections.
- `scripts/render_video.py`: joins canonical scene clips into a final video.
- `scripts/render_text.py`, `scripts/apply_watermark.py`, and `scripts/add_loop.py`: optional post-production passes.
- `app/`: provides local command interfaces over maintained project utilities.

Operational rules, retry limits, continuity handling, and review decisions are defined in `AGENTS.md` and the project-local skills.

## Basic usage

Preview generation without consuming quota:

```bash
python3 scripts/generate_scenes.py \
  --config stories/<story-slug>/scenes.json \
  --dry-run
```

Generate scenes for a story:

```bash
python3 scripts/generate_scenes.py \
  --config stories/<story-slug>/scenes.json
```

Render its canonical clips:

```bash
python3 scripts/render_video.py \
  --config stories/<story-slug>/scenes.json \
  --output stories/<story-slug>/output/final-video.mp4
```

Generation uses Google Cloud Application Default Credentials when available, otherwise `GEMINI_API_KEY`. Credentials must not be copied into the repository.
