---
name: gemini-omni-flash-api
description: Execute Gemini Omni video generation, image/video-reference generation, editing, extension, first/last-frame workflows, and stateful follow-up turns through the project-local google-genai adapter. Use after the final Omni prompt is already authored. Do not use for video inspection, transcoding, contact sheets, scene direction, or prompt compilation.
---

# Gemini Omni Flash API

Use this skill only for **Omni capability truth and request execution**. The creative prompt should already be final before invoking it.

For scene direction use `direct-video-scene`. For Omni prompt authoring use `compile-omni-scene`. For media inspection, trimming, transcoding, contact sheets, or other deterministic video work use `ffmpeg-skill`.

## Canonical executable

From the repository root:

```bash
python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
  --prompt "<final Omni prompt>" \
  --output media/output.mp4
```

The project adapter is:

```text
.agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py
```

## Authentication and model routing

- Default project model: `gemini-omni-1.1-flash-preview` through the machine's existing Vertex/ADC project in `global`.
- `gemini-omni-1.1-flash` can be selected explicitly with `--model` and uses existing Gemini Developer API credentials when quota is available.
- Do not add, print, or request credential arguments. Use the existing local credentials.

## Core invocation patterns

### Text to video

```bash
python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
  --prompt "<final prompt>" \
  --duration 8 \
  --aspect-ratio 16:9 \
  --resolution 720p \
  --output media/output.mp4
```

### First frame

```bash
python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
  --prompt "<final prompt>" \
  --first-frame media/start.png \
  --output media/output.mp4
```

### First + last frame

```bash
python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
  --prompt "<final prompt>" \
  --first-frame media/start.png \
  --last-frame media/end.png \
  --output media/output.mp4
```

### Image references

```bash
python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
  --prompt "@hero walks into <IMAGE_REF_1>." \
  --image hero=media/hero.png \
  --image location=media/location.png \
  --output media/output.mp4
```

Friendly aliases are local convenience only:

```text
--image dog.png       => @dog or <IMAGE_REF_0>
--image hero=dog.png  => @hero or <IMAGE_REF_0>
--video-reference walk.mp4 => @walk or <VIDEO_REF_0>
```

Native Omni references remain supported:

```text
<FIRST_FRAME>
<LAST_FRAME>
<IMAGE_REF_N>
<VIDEO_REF_N>
```

Aliases and native references may be mixed. The adapter expands aliases before sending the request to Google.

### Edit an uploaded video

```bash
python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
  --prompt "<edit instruction>" \
  --video media/input.mp4 \
  --output media/edited.mp4
```

Use `--strip-audio` only when the source video's audio should be removed before Omni receives it so fresh audio can be generated. The adapter performs that one preparation step internally.

### Extend an uploaded video

```bash
python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
  --prompt "Extend this video. <continuation>" \
  --extend media/input.mp4 \
  --output media/extended.mp4
```

### Stateful follow-up

Prefer metadata when later turns may be needed:

```bash
python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
  --prompt "<final prompt>" \
  --output media/output.mp4 \
  --metadata-out media/output.json \
  --json
```

Then use `--previous-result` or `--previous-interaction-id` for supported stateful follow-up operations.

## Request controls

The adapter exposes:

```text
--duration 3..10
--aspect-ratio 16:9|9:16
--resolution 360p|720p|1080p|4k
--first-frame PATH
--last-frame PATH
--image / --image-reference / --image-ref [ALIAS=]PATH
--video-reference / --video-ref [ALIAS=]PATH
--video PATH
--extend PATH
--previous-result PATH
--previous-interaction-id ID
--operation edit|extend
--task text_to_video|image_to_video|reference_to_video|edit|extend
--delivery auto|inline|uri
--store / --no-store
--strip-audio
--dry-run
--capabilities
--metadata-out PATH
--json
```

Normally omit `--task` and let Omni infer the operation unless an explicit task is required by the selected surface/workflow.

## Current execution contract

Use `--capabilities` for machine-readable current limits instead of duplicating changing values elsewhere:

```bash
python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py --capabilities
```

Important stable expectations in this project:

- one output video per interaction;
- output aspect ratios: `16:9`, `9:16`;
- output duration: 3–10 seconds per generation;
- output resolutions: 360p, 720p, 1080p, 4K;
- first-frame and first+last-frame workflows are supported;
- uploaded-video editing is supported;
- video extension is supported, but exact extension semantics differ between Developer API and Cloud preview;
- stateful interactions return an `interaction_id` when stored;
- reference videos are for reference, not source editing; their audio is ignored;
- voice editing is not supported by this adapter's documented Omni workflow.

When a capability is consequential or may have changed, trust `--capabilities` and the current Google source rather than remembered values.

## Execution discipline

1. Receive a complete final prompt; do not re-direct or rewrite the scene here.
2. Bind only the references actually required by that prompt.
3. Use `--dry-run` when bindings are non-trivial or before an expensive request.
4. Prefer `--metadata-out` / `--json` when later edit or extension is possible.
5. If input media needs inspection, trimming, resizing, normalization, contact sheets, or general transcoding, use `ffmpeg-skill` before calling this skill.
6. Do not retry paid generation blindly after backend/quota/platform failures. Inspect the returned error first.

## Source

This project skill is based on Google's `gemini-omni-flash-api` skill from `google-gemini/gemini-skills`. See `SOURCE.md` for the pinned upstream commit and local adaptation notes.
