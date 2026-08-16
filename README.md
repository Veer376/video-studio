# Video Project

A Gemini Omni Flash production workspace for planning a story as short clips, reviewing attempt candidates, selecting one canonical video per scene, and joining the selected clips with FFmpeg.

The project-local `produce-omni-story` skill orchestrates the workflow. It delegates every Omni prompt, prompt revision, and prompt diagnosis to the shared `omni-flash-prompt-writer` skill; this repository does not duplicate model-specific prompt rules.

## Project layout

```text
assets/characters/                    reusable character references
stories/<story-slug>/story.md         creative contract, parts, and clip briefs
stories/<story-slug>/characters.json  recurring character references
stories/<story-slug>/scenes.json      final authoring prompts and scene inputs
stories/<story-slug>/assets/          story-specific assets
stories/<story-slug>/videos/          canonical scene MP4s
stories/<story-slug>/temp/            continuity frames and review evidence
stories/<story-slug>/reviews/         review decision per scene
stories/<story-slug>/output/          final renders
youtube/                               branding, thumbnails, and promotion assets
scripts/                               generation and rendering entry points
```

Reusable assets remain at project level. Story directories contain only story-specific assets and production state.

The current story is [`stories/aloo-flood-rescue/story.md`](stories/aloo-flood-rescue/story.md).

## Sources of truth

- `story.md` owns story-specific creative intent, pacing, structure, and clip briefs.
- `characters.json` maps only recurring, consistency-critical `@handles` to reusable reference images.
- `scenes.json` owns the final authoring prompts and generation inputs.
- `reviews/<scene-id>.json` owns the observable review decision for one generated scene.
- Each scene's `output_path` is its only canonical video.

Rough discussion is not stored as `rough_brief`. There is no stored `extended_prompt`, dialogue metadata, take system, or render manifest.

## Workflow

1. Create or update the selected story's creative contract, parts, and clip briefs in `story.md`.
2. Choose the working scope: complete story, one part, or one clip.
3. Create every clip prompt independently with `omni-flash-prompt-writer` and persist it in `scenes.json`.
4. Generate each selected clip as an attempt candidate under `temp/partial/`. Existing valid canonical videos are skipped by default.
5. Validate each candidate, review its visual and audio evidence, and append the attempt under `reviews/`.
6. Promote the reviewed selected attempt to the canonical `videos/` path. Repair only diagnosed material defects, then render the canonical clips.

A dependent scene is produced only after its predecessor's reviewed selection has been promoted, its canonical hash has been verified, and its exact final frame has been inspected.

## Scene references

Project `@handles` are authoring syntax, not Gemini API parameters. Before an API call, the runner resolves handles in first-appearance order to the corresponding character images and replaces them with `<IMAGE_REF_N>` tags. Other `reference_images` may represent objects, locations, styles, or other visual guidance.

`reference_scene_id` means that the previous scene's final frame is the literal opening anchor for the current scene. The runner extracts it and binds it as `<FIRST_FRAME>`. An inspected corrected still may be supplied with `first_frame_path` when carrying the raw final frame forward would propagate a visible defect.

The project relies on the current `omni-flash-prompt-writer` skill and official Google documentation for model capabilities. Do not infer new API behavior from this README.

## Generate scenes

Preview the default story without using generation quota:

```bash
python3 scripts/generate_scenes.py --dry-run
```

Select another story or a smaller scope:

```bash
python3 scripts/generate_scenes.py --config stories/<story-slug>/scenes.json --dry-run
python3 scripts/generate_scenes.py --part part_01
python3 scripts/generate_scenes.py --scene s001
```

Generate attempt 1 for all missing scenes:

```bash
python3 scripts/generate_scenes.py
```

Generate a diagnosed retry without changing the existing canonical clip:

```bash
python3 scripts/generate_scenes.py --scene s001 --attempt 2 --regenerate
```

The runner stores attempts as `temp/partial/<scene-id>-attempt-<number>.mp4`. After reviewing a candidate, persist its review with `selected_attempt`, then promote it:

```bash
python3 scripts/generate_scenes.py --scene s001 --promote-attempt 2 --dry-run
python3 scripts/generate_scenes.py --scene s001 --promote-attempt 2
```

Promotion requires complete attempt evidence, a media-valid selected candidate, and a promotable review decision. It records the canonical SHA-256 in the review so dependent scenes and the renderer can reject stale or externally replaced videos. `best_available` is promotable only when its review records explicit autonomous execution.

Each scene receives one initial attempt and at most two diagnosed retries. Interactive work stops if all three fail. When the user explicitly requests autonomous continuation, the agent compares the media-valid candidates, records the strongest failed attempt as `best_available` with its unresolved defects, promotes it, and continues. It still stops when no media-valid candidate exists.

## Render

```bash
python3 scripts/render_video.py --dry-run
python3 scripts/render_video.py
```

The default output is `stories/aloo-flood-rescue/output/final-video.mp4`. Select another configuration or output when needed:

```bash
python3 scripts/render_video.py \
  --config stories/<story-slug>/scenes.json \
  --output stories/<story-slug>/output/final-video.mp4
```

The renderer requires a renderable persisted review for every canonical scene and validates every input and the completed output with `ffprobe`.

Add optional timed text in a separate pass without changing the canonical scene renderer:

```bash
python3 scripts/render_text.py \
  --input stories/<story-slug>/output/final-video.mp4 \
  --output stories/<story-slug>/output/final-video-with-text.mp4 \
  --text "One Hour Before..." \
  --start 21 \
  --duration 3
```

## Authentication and isolated tests

Generation uses Google Cloud Application Default Credentials when available, otherwise `GEMINI_API_KEY`. Credentials are never copied into this repository.

Use `scripts/main.py` only for isolated single-prompt experiments:

```bash
python3 scripts/main.py \
  --prompt "10-second single continuous shot ..." \
  --output tests/videos/example.mp4 \
  --aspect-ratio 16:9
```

Run the automated tests with:

```bash
python3 -m unittest discover -s tests -v
```
