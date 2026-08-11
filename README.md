# Video Project

An experimental, API-driven pipeline for building a story from short Gemini Omni Flash clips and joining the approved clips with FFmpeg.

Project-specific model behavior and recovery patterns are recorded in [`OMNI_FINDINGS.md`](OMNI_FINDINGS.md).

## Project layout

```text
assets/characters/                 reusable character references
stories/<story-slug>/story.md      creative contract, parts and scene briefs
stories/<story-slug>/characters.json
stories/<story-slug>/scenes.json   executable production prompts
stories/<story-slug>/videos/       canonical scene MP4s
stories/<story-slug>/temp/         continuity frames and review media
stories/<story-slug>/reviews/      future reviewer decisions
stories/<story-slug>/output/       final renders
youtube/                            branding, thumbnails and promotion assets
```

The current story slug is `aloo-flood-rescue`. Reusable assets remain at project level; every story references them using explicit project-relative paths.

## Workflow

1. Describe the story and each rough scene manually.
2. Convert every rough scene into a production prompt with the `omni-flash-prompt-writer` skill.
3. Define handles, names, and reference paths only for recurring characters whose appearance must stay consistent across clips.
4. Store each production prompt, its subject handles, additional ordered reference images, and optional previous-scene reference in the story's `scenes.json`.
5. Resolve subject handles to Gemini image-reference tags at request time and generate each clip with `gemini-omni-flash-preview`.
6. Review the canonical scene MP4 files, regenerate individual scenes when necessary, then concatenate them with FFmpeg into the final video.

The current structures are stored in `stories/aloo-flood-rescue/characters.json` and `stories/aloo-flood-rescue/scenes.json`. A scene has this minimal form:

```json
{
  "model": "gemini-omni-flash-preview",
  "aspect_ratio": "16:9",
  "characters_file": "stories/aloo-flood-rescue/characters.json",
  "scenes": [
    {
      "id": "s001",
      "prompt": "@aloo moves rapidly through the tilting train while @gajar pulls the children back.",
      "subjects": ["@aloo", "@gajar"],
      "reference_images": [],
      "reference_scene_id": null,
      "output_path": "stories/aloo-flood-rescue/videos/s001.mp4"
    },
    {
      "id": "s002",
      "prompt": "<FIRST_FRAME> @aloo grabs the emergency rope and lunges toward @chhotu.",
      "subjects": ["@aloo", "@chhotu"],
      "reference_images": [],
      "reference_scene_id": "s001",
      "output_path": "stories/aloo-flood-rescue/videos/s002.mp4"
    }
  ]
}
```

The manual rough brief is conversation input, not durable pipeline data, so there is no `rough_brief`. There is also no stored `extended_prompt`: `prompt` keeps readable project handles and is resolved only in memory at request time.

## Reference-image semantics

Gemini Omni Flash has no separate character-reference parameter. This project adds a small authoring layer: `characters.json` maps recurring, consistency-critical `@handles` to image paths, while the API still receives ordinary ordered image inputs. One-off characters and flexible story elements such as the River are described directly in prompts rather than registered. Other reference images can represent products, objects, styles, locations, storyboards, or motion guides.

Keep the mapping simple:

- `characters.json` stores only `handle`, `name`, and `reference_path` for each recurring character that needs cross-clip consistency.
- `subjects` lists the handles used by a scene; every listed handle must appear in its prompt.
- `reference_images` stores any additional non-character images in upload order.
- At request time, handles are resolved in first-appearance order to `<IMAGE_REF_0>`, `<IMAGE_REF_1>`, and so on.
- Put useful action-specific characteristics next to a handle only when needed; the reference image owns stable appearance.
- Square brackets are only a readable prompt convention; they are not a special API feature.
- The Gemini API does not provide a separate description field for each image. Image meaning belongs in the prompt.
- Do not send project `@handles` directly to the Gemini API. Google documents `<IMAGE_REF_N>` for references and `<FIRST_FRAME>` for a literal starting frame.

## Continuity model

Gemini Omni Flash does **not** currently support true video extension or first/last-frame interpolation in the public API. A scene therefore must not pass the complete previous clip as a Veo-style extension input.

For a scene with `reference_scene_id`, the pipeline will:

1. Extract the final frame of the previous scene's canonical MP4 with FFmpeg.
2. Pass that frame as the first uploaded image and bind it as `<FIRST_FRAME>` in `prompt`.
3. Resolve scene `subjects` from `characters.json`, then append any additional `reference_images`; bind all loose references as `<IMAGE_REF_0>`, `<IMAGE_REF_1>`, and so on.

Use `reference_scene_id` only when continuity matters. It gives the next clip a visual starting anchor, but it is not a guarantee of exact identity, motion, or spatial continuity.

If the extracted final frame contains visible identity drift, set an optional project-relative `first_frame_path` on the next scene. The pipeline still validates `reference_scene_id` as the story dependency, but uses the curated still as `<FIRST_FRAME>` instead of extracting the corrupted frame again. Use this override only for an inspected corrective frame that preserves the previous composition.

## Current Gemini Omni Flash API constraints

Verified against Google's Gemini API documentation on 2026-08-10:

- Model: preview `gemini-omni-flash-preview` via the Interactions API.
- Output: 3–10 seconds, 720p, 24 FPS; aspect ratio `16:9` or `9:16`.
- Supported tasks: `text_to_video`, `image_to_video`, `reference_to_video`, and `edit`.
- First-frame images and subject/style/object image references are supported. The Gemini Developer API guide shows six image references without publishing a hard maximum; Gemini Enterprise Agent Platform documents a maximum of 10 images per prompt.
- Stateful editing of an Omni-generated result is supported through `previous_interaction_id` when the interaction is stored.
- Uploaded videos up to 10 seconds can be edited where region/input rules permit. The Agent Platform schema allows at most three videos per prompt, but the current Gemini API says video references are not processed correctly and multiple-video reasoning is unsupported, so this project will not use video references for scene continuation.
- Uploaded audio references, voice editing, video extension, and video interpolation are unsupported in the public API.
- English is fully supported; other languages may work but are not evaluated to the same level.
- Generated clips contain SynthID watermarking. Exact character identity, exact text, and complex motion still require visual review.

Official references: [Gemini Omni Flash guide](https://ai.google.dev/gemini-api/docs/omni), [Gemini API model reference](https://ai.google.dev/gemini-api/docs/models/gemini-omni-flash), [Agent Platform model limits](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/omni-flash-preview), and [DeepMind prompt guide](https://deepmind.google/models/gemini-omni/prompt-guide/).

## Generate scenes

`generate_scenes.py` reads the selected story's `scenes.json`, validates every referenced character asset, compiles project `@handles` into ordered Gemini image references, and saves one canonical MP4 per scene. Its default is the current `aloo-flood-rescue` story. Preview the work without using generation quota:

```bash
python3 generate_scenes.py --dry-run
```

Select another story explicitly:

```bash
python3 generate_scenes.py --config stories/<story-slug>/scenes.json --dry-run
```

Generate every missing scene:

```bash
python3 generate_scenes.py
```

Limit a run when refining one part or scene:

```bash
python3 generate_scenes.py --part part_01
python3 generate_scenes.py --scene s001
```

Each scene has one `output_path`:

```text
stories/aloo-flood-rescue/videos/
  s001.mp4
  s002.mp4
```

Existing scene videos are verified and skipped by default. To replace one deliberately:

```bash
python3 generate_scenes.py --scene s001 --regenerate
```

The presence of a valid `output_path` file is the generation state; no separate take manifest or mutable JSON status is maintained. Regeneration writes a temporary partial file, validates its video and audio streams, and only then atomically replaces the previous MP4. If a scene has `reference_scene_id`, generation waits for that earlier scene's canonical MP4, extracts its final frame into a temporary directory, and supplies it as `<FIRST_FRAME>`. The temporary image is removed automatically. The final renderer can concatenate scene `output_path` files in `scenes.json` order.

## Render the complete video

`render_video.py` validates every canonical scene, performs a first FFmpeg pass that concatenates all scenes directly with no inserted black screen, then performs a second FFmpeg pass that overlays the title directly on the finished video timeline. The title is bottom-right and remains visible for three seconds:

```bash
python3 render_video.py --dry-run
python3 render_video.py
```

The default title is `One Hour Before...`, overlaid on the finished video from 21.0s to 24.0s. Override the title or timing when needed:

```bash
python3 render_video.py \
  --title "One Hour Before..." \
  --title-start 21.0 \
  --title-duration 3.0 \
  --output stories/aloo-flood-rescue/output/final-video-01.mp4
```

By default, the script writes to the selected story's `output/final-video.mp4`. It uses a temporary partial render, validates its video and audio streams with `ffprobe`, and promotes it only after successful validation.

## Setup

The test generator reuses the authentication already available to `video-story-studio`: Google Cloud Application Default Credentials (ADC) when present, otherwise the Gemini Developer API key. No credential is copied into this repository. The `auto` backend prefers ADC because Omni Flash has no free-tier request quota on the configured Developer API key.

```bash
python3 main.py \
  --prompt "10-second single continuous unbroken shot ..." \
  --output tests/videos/example.mp4 \
  --aspect-ratio 16:9
```

Select a backend explicitly when needed:

```bash
python3 main.py --backend vertex --gcp-project YOUR_PROJECT_ID ...
export GEMINI_API_KEY="..."
python3 main.py --backend developer ...
```

Optional image references can be supplied in upload order:

```bash
python3 main.py \
  --prompt "[# Sources <FIRST_FRAME>@Image1] [# References <IMAGE_REF_0>@Image2] ..." \
  --image stories/aloo-flood-rescue/videos/s001-last-frame.png \
  --image assets/references/ravi.png \
  --task reference_to_video \
  --output tests/videos/continued-scene.mp4
```

The scene runner automatically checks for both video and audio streams with `ffprobe` before promoting a partial download to the canonical scene MP4. Use `main.py` only for isolated single-prompt experiments.

For an isolated uploaded-video edit, supply one short video and use a surgical prompt. Save to a separate path and inspect it before replacing a canonical scene:

```bash
python3 main.py \
  --video stories/aloo-flood-rescue/videos/s014.mp4 \
  --task edit \
  --prompt "Remove only the duplicate character. Keep the original camera, movement, timing, lighting, and audio unchanged. Keep everything else the same." \
  --output tests/videos/s014-edited.mp4
```
