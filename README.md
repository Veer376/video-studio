# Video Project

A Gemini Omni Flash production workspace for planning a story as short clips, generating one canonical video per scene, reviewing the results, and joining accepted clips with FFmpeg.

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
4. Generate the selected missing clips. Existing valid canonical videos are skipped by default.
5. Validate each new MP4, review its visual and audio evidence, and persist the decision under `reviews/`.
6. Repair only diagnosed material defects, then render the requested canonical clips.

A dependent scene is produced only after its referenced predecessor exists and its exact final frame has been inspected.

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

Generate all missing scenes:

```bash
python3 scripts/generate_scenes.py
```

Replace one scene only after regeneration is explicitly authorized:

```bash
python3 scripts/generate_scenes.py --scene s001 --regenerate
```

The runner writes a partial file, verifies its video and audio streams, and promotes it only after validation succeeds.

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

The renderer validates every canonical input and the completed output with `ffprobe`.

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
