# Production Pipeline Stage

This stage owns production execution guidance. It does not contain production code. The project pipeline owns execution, retries, and validation.

Use this skill after the creative stages have produced:

- `library/<project_name>/session.json`
- `library/<project_name>/script.md`
- `library/<project_name>/scenes.json`

The default production flow is:

```text
voice -> illustrate -> render
```

If `audio/directions.json` exists, voice reads its per-scene Gemini audio tags. It validates that removing tags leaves the exact clean `scenes.json.text`; alignment and subtitles always use the clean scene text.

## Naming Contract

- `image-story`: master skill and workflow owner.
- `story-video`: production CLI executable.
- `voice -> illustrate -> render`: unnamed default production flow.

## Commands

Inspect state:

```bash
story-video status library/<project_name>
```

Run or resume the full default pipeline:

```bash
story-video run library/<project_name>
```

Run one stage:

```bash
story-video stage voice library/<project_name>
story-video stage illustrate library/<project_name>
story-video stage render library/<project_name>
```

Illustration has two resumable phases. Normal `illustrate` runs both in order:

```bash
story-video stage illustrate library/<project_name> --illustration-phase characters
story-video stage illustrate library/<project_name> --illustration-phase scenes
```

The character phase creates missing canonical assets under project `assets/characters/`. A `root:assets/...` character with `prompt: null` is reused directly; with a non-null prompt it is adapted into a project-local asset and the manifest is updated after success. The scene phase uses canonical assets plus a compatible prior scene when available. The configured provider receives at most four ordered references; production owns that allocation.

Repository defaults live in `kathamind/config.json` under `production`:

```json
{
  "_comment": "image_provider: cloudflare|flow|google; subtitles/zoom/closing_fade: true|false; short overrides render settings for Shorts",
  "image_provider": "flow",
  "image_model": "pro",
  "subtitles": false,
  "zoom": true,
  "closing_fade": true,
  "short": {
    "subtitles": false,
    "closing_fade": false
  }
}
```

Supported image providers are `cloudflare`, `flow`, and `google`. Flow's `lite` alias maps to the free `harbor_seal` model, `standard` maps to `narwhal`, and `pro` maps to `gem_pix_2`. Flow uses the local `flow-agent` backend and Chrome extension, including ordered reference-image uploads for character and previous-scene continuity. The `short` object overrides `subtitles`, `zoom`, and `closing_fade` for `9:16` projects targeting at most 180 seconds; otherwise the base values apply. `closing_fade` controls whether the video is extended by 2 seconds at the end and faded out gradually to black (default `true` for long videos, disabled for Shorts). Provider and model are never stored in `session.json`.

An outer pipeline invocation may temporarily override its internal stages:

```bash
story-video run library/<project_name> \
  --image-provider flow \
  --image-model pro \
  --subtitles \
  --no-zoom \
  --no-closing-fade \
  --force-stage illustrate \
  --force-stage render
```

Without these flags, `kathamind/config.json` supplies the defaults. Overrides do not mutate project state. If the affected stage is already complete or has cached artifacts, use `--force` or the matching `--force-stage`; the pipeline rejects an override that would otherwise be ignored. After editing repository defaults, force each affected stage because cached artifacts are not automatically invalidated.

For Flow, start the local backend with `~/.local/bin/flow`, keep the Flow Agent Chrome extension connected, and open/refresh Google Flow while signed in so the bearer key is captured. `image_model: lite` is the free image path and supports ordered local reference images for continuity.

For Google, set `image_provider` to `google`, set `image_model` to `gemini-3.1-flash-image`, and configure Application Default Credentials plus `GOOGLE_CLOUD_PROJECT` before illustration.

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

- every registered character has a valid project-local image or an approved `root:assets/...` shared image
- every character referenced by a generated scene has a valid canonical image on disk
- every scene has `image_path`
- every referenced image exists on disk

`render` is complete when:

- `output/final-video.mp4` exists
- `ffprobe` confirms video and audio streams
- for a `9:16` project with `brief.target_duration_seconds <= 180`, `ffprobe` confirms the final duration is `<= 180.000` seconds

## Short Duration Gate

After rendering a `9:16` project with `brief.target_duration_seconds <= 180`, read the final media duration:

```bash
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 library/<project_name>/output/final-video.mp4
```

If the result is greater than `180.000` seconds:

- Do not report the render or project as complete.
- Return to `compose` and compress the script while preserving its hook and payoff.
- After the revised script and scenes are approved, regenerate affected downstream artifacts and verify again.
- Never solve the failure by accelerating narration or truncating the ending.

## Hard Rules

- Use `story-video run` for normal resumes.
- Use `story-video stage illustrate` for missing-only image retries.
- Use `--force` or `--force-stage` only when the user asks to regenerate work.
- Do not call production scripts from skill folders; production implementation lives under `src/studio/` and is invoked through `story-video`.
- Do not skip `voice` before render; render depends on narration audio and timestamps.
- Never accept a Short over `180.000` seconds as complete.
