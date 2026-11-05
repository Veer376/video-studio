# Image story

Narrated, captioned stories built from primary illustrations, continuation stills, and optional generated motion. The newer `produce-visuals` engine is the primary visual path; `render-story` assembles its manifest-backed output.

## Install and render the offline example

From this directory:

```bash
uv sync --locked --python 3.12
uv run --locked produce-visuals plan examples/offline
uv run --locked render-story --project-dir examples/offline --dry-run
uv run --locked render-story --project-dir examples/offline --width 640 --height 360 --fps 24
```

Requires FFmpeg/FFprobe. Output: `examples/offline/output/final-video-no-bgm.mp4` (8 seconds). Fixture audio is a synthetic tone; the six caption words are illustrative test timings. No provider calls occur.

## Generate a new story

Configure credentials as described in [setup](../../docs/setup.md), then copy the editable template:

```bash
mkdir -p work
cp -R examples/template work/my-story
```

Edit `session.json` to lock aspect ratio/style and voice language. Edit `scenes.json`: each scene needs a unique ID, spoken `text`, content-only `image_prompt`, optional continuation prompts, and continuity references. `continuity.json` owns recurring identities/locations; the template is empty. The skills in `.agents/skills/` support writing and visual planning with an agent, or author these files manually.

Generate narration and timestamps in three explicit stages:

```bash
uv run --locked story-video voice-step narrate work/my-story
uv run --locked story-video voice-step transcribe work/my-story
uv run --locked story-video voice-step align work/my-story
```

Narrate/transcribe call paid external services. Alignment is local, writes scene start/end times and inclusive word indices, and emits `audio/timestamps.json`. Listen to narration and inspect alignment before proceeding. The template's scene durations are planning estimates, not speech timestamps.

Plan before generating images:

```bash
uv run --locked produce-visuals plan work/my-story
uv run --locked produce-visuals run work/my-story --images-only --dry-run
uv run --locked produce-visuals run work/my-story --images-only --image-provider google --image-model gemini-3.1-flash-image
uv run --locked produce-visuals status work/my-story
```

Only the non-dry `run` calls image generation. Inspect outputs. Rerunning reuses verified current assets; changed prompts/style/references invalidate dependencies. Read [visual production](scripts/production/README.md) for continuity approvals, selected-scene execution, durable state, and optional authored video maps. Optional video generation is separate and billable; it is not enabled by `--images-only`.

Render after narration, timestamps, and media are complete:

```bash
uv run --locked render-story --project-dir work/my-story --dry-run
uv run --locked render-story --project-dir work/my-story
```

Output: `work/my-story/output/final-video-no-bgm.mp4`. The renderer uses `audio/narration.wav` (or legacy MP3), the production manifest, scene timings/word indices, and captions. It does not add background music. Inspect playback and audio; use `--force` to rebuild caches after editing upstream files.

## Compatibility path

`story-video status/run/stage` remains available for existing productions using its older illustration/render artifact contract. New primary projects should use `voice-step`, `produce-visuals`, and `render-story` above. Legacy defaults are in this directory's `config.json`; they do not configure the newer producer. Cloudflare is supported by the older illustration adapter only. See [recovery](../../docs/recovery.md) before regeneration.
