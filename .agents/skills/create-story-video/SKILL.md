---
name: create-story-video
description: Create narrated image-based storytelling videos from a structured story manifest. Use when Antigravity needs to write a story, split it into timed scenes, generate scene images, prepare narration audio, render Ken Burns-style clips, burn subtitles, mix music, and export MP4 story videos. Supports Antigravity built-in ImageGen (generate_image tool), manual image assets, existing audio, and extensible voice/image providers.
---

# Create Story Video

Use this skill to create a resumable project directory for narrated, image-based story videos. Keep generated media in the project/output directory, never inside this skill folder.

Default project: `/Users/aryaveer/Projects/story-video-maker`.

## Core Boundary

- In `antigravity` (default) image mode, generate scene images directly using the `generate_image` tool, save the output files to `generated/images/`, and update `story.json`.
- Keep the prompts highly descriptive, structuring composition, character continuity, and visual styling.
- Python only receives ordinary file paths for images, audio, fonts, music, and manifests.

## Workflow

1. Inspect the project directory and any local instructions.
2. Ask for or infer these project controls before writing scenes: target duration, target image/scene count, image provider, voice provider, and whether subtitles are enabled.
3. Create or update a readable `story.json` manifest. See [story-schema.md](file:///Users/aryaveer/Projects/story-video-maker/.agents/skills/create-story-video/references/story-schema.md) or the global equivalent.
4. Write a compact character bible before any scene image prompts. See [image-continuity.md](file:///Users/aryaveer/Projects/story-video-maker/.agents/skills/create-story-video/references/image-continuity.md) or the global equivalent.
5. Divide the story into exactly the configured number of image scenes unless the user approves a different count.
6. Run deterministic validation and preparation with `scripts/run_video_pipeline.py`.
7. For missing images:
   - `manual`: ask for or use supplied image paths.
   - `antigravity` (default): generate images using the `generate_image` tool, save into `generated/images/`, and update `story.json`.
8. For narration:
   - `existing_audio`: validate scene audio files.
   - `gemini_tts` (recommended): use after `GEMINI_API_KEY` is set in the environment (or uses hardcoded fallback key); supports natural voice names like `Puck`, `Aoede`, `Charon`, `Kore`, `Fenrir` with custom style/mood/emotion tags (e.g. `[excitedly]`, `[whispers]`) inside the text.
   - `groq_tts`: use only after `GROQ_API_KEY` is present in the environment; generate one audio file per scene and measure it with ffprobe.
   - `sarvam_tts`: use only after `SARVAM_API_KEY` is present in the environment; prefer it for Hindi narration and use `transport=rest_stream` by default.
   - future providers must follow the same per-scene file contract.
9. Measure each scene audio with ffprobe and write exact `duration_seconds`.
10. Render scenes, optional subtitles, music mix, and final MP4 with the project Python pipeline.
11. Re-run without `--force` to verify caching and resumability.

## Commands

From a project using the bundled renderer:

```bash
cd /Users/aryaveer/Projects/story-video-maker
PYTHONPATH=src python3 -m story_video.cli validate story.json
PYTHONPATH=src python3 -m story_video.cli prepare story.json
PYTHONPATH=src python3 -m story_video.cli voice-preview story.json --voice-gender female --force
PYTHONPATH=src python3 -m story_video.cli voice-preview story.json --voice-gender male --force
PYTHONPATH=src python3 -m story_video.cli voice story.json --force
PYTHONPATH=src python3 -m story_video.cli pace story.json --force
PYTHONPATH=src python3 -m story_video.cli render story.json --force
```

Use `--force` only for assets or clips the user explicitly wants regenerated.

## Image Prompt Rules

Use provider-independent prompts. Include recurring character details, visual style, scene composition, cultural constraints, and avoid lists. Never ask the image model to render text inside images for this workflow.

For the Hindi Krishna-inspired MVP, preserve:

- Nandan: 24, warm brown skin, shoulder-length dark wavy hair, off-white dhoti, muted rust angavastram, simple sandals.
- Krishna: youthful Indian man, deep blue skin, long dark hair, one peacock feather, golden-yellow pitambara, simple ornaments, bamboo flute, no large crown.
- Style: ancient rural India, premium cinematic digital painting, warm ochre, saffron, muted teal, peacock blue, warm gold.
- Avoid: modern objects, text, watermarks, neon aura, theatrical poster treatment, unnecessary supernatural effects.

## Validation

Before calling the MVP complete, verify:

- `story.json` is valid and readable.
- Each scene has one image, one audio segment, and measured duration.
- If subtitles are enabled, Hindi subtitles burn correctly with a Devanagari-compatible font.
- The final MP4 probes successfully and plays for the expected duration.
- Re-running without `--force` reuses existing valid assets.

## Project Map

Read [PROJECT.md](file:///Users/aryaveer/Projects/story-video-maker/PROJECT.md) when you need exact output folders, generated asset locations, or user-runnable commands.
