---
name: run-pipeline
description: Single production pipeline runner for Story Video Maker. Use after creative files exist to resume or run voice, Cloudflare illustration, and render through the project CLI.
---

# Run-Pipeline Skill

This is the only agent-facing skill for production execution. It does not contain production code. The project pipeline owns execution, retries, and validation.

Use this skill after the creative stages have produced:

- `library/<project_name>/session.json`
- `library/<project_name>/script.md`
- `library/<project_name>/scenes.json`

The current production pipeline is `image-story`:

```text
voice -> illustrate -> render
```

Cloudflare is the only image backend for now. Do not use Codex `imagegen` in this pipeline unless the project adds that provider later.

## Naming Contract

- `Story Video Maker`: product/repository name.
- `create-image-story`: master skill for the complete creative + production workflow.
- `run-pipeline`: production-only skill.
- `story-video`: project CLI executable.
- `image-story`: current image-based production pipeline.

## Commands

Inspect state:

```bash
story-video status library/<project_name>
```

Run or resume the full default pipeline:

```bash
story-video run library/<project_name>
```

Run the named pipeline explicitly:

```bash
story-video pipeline image-story library/<project_name>
```

Run one stage:

```bash
story-video stage voice library/<project_name>
story-video stage illustrate library/<project_name>
story-video stage render library/<project_name>
```

Retry missing image generation only:

```bash
story-video stage illustrate library/<project_name>
```

Force regenerate all images:

```bash
story-video stage illustrate library/<project_name> --force
```

Force one stage while resuming the rest:

```bash
story-video run library/<project_name> --force-stage illustrate
```

## Resume Rules

The project pipeline computes state from files, not only `session.json`.

`voice` is complete when:

- `audio/narration.wav` exists
- `audio/timestamps.json` exists
- every scene has float `start_time` and `end_time`

`illustrate` is complete when:

- every scene has `image_path`
- every referenced image exists on disk

`render` is complete when:

- `output/final-video.mp4` exists
- `ffprobe` confirms video and audio streams
- when `brief.target_duration_seconds <= 60`, `ffprobe` confirms the final duration is `<= 60.000` seconds

## Short Duration Gate

After rendering a project with `brief.target_duration_seconds <= 60`, read the final media duration:

```bash
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 library/<project_name>/output/final-video.mp4
```

If the result is greater than `60.000` seconds:

- Do not report the render or project as complete.
- Return to `compose` and compress the script while preserving its hook and payoff.
- After the revised script and scenes are approved, regenerate affected downstream artifacts and verify again.
- Never solve the failure by accelerating narration or truncating the ending.

## Hard Rules

- Use `story-video run` for normal resumes.
- Use `story-video stage illustrate` for missing-only image retries.
- Use `--force` or `--force-stage` only when the user asks to regenerate work.
- Do not call scripts under `.agents/skills/*/scripts`; production scripts live under `src/studio/scripts`.
- Do not skip `voice` before render; render depends on narration audio and timestamps.
- Never accept a Short over `60.000` seconds as complete.
