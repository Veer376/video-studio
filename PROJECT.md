# Story Video Maker

Project path after promotion: `/Users/aryaveer/Projects/story-video-maker`.

## Layout

- `src/story_video/`: renderer, manifest, audio providers, FFmpeg helpers.
- `story.json`: current prototype manifest and provider settings.
- `config.yaml`: project render defaults.
- `assets/`: user-provided references, music, fonts. These folders are tracked with `.gitkeep`.
- `generated/images/`: final scene images consumed by the renderer.
- `generated/audio/`: raw generated narration files.
- `generated/audio/paced/`: paced narration files used after timing adjustment.
- `generated/audio/previews/`: short voice samples.
- `generated/scenes/`: rendered scene clips.
- `generated/subtitles/`: optional subtitle files/overlays.
- `generated/temp/`: intermediate concat/audio/frame files.
- `output/final-video.mp4`: final render.
- `scripts/run_video_pipeline.py`: project-local runner for the CLI.

Generated media is ignored by git but kept locally. Commit source, manifests, configs, tests, and skill updates.

## Commands

```bash
PYTHONPATH=src python3 -m story_video.cli validate story.json
PYTHONPATH=src python3 -m story_video.cli voice-preview story.json --voice-gender female --force
PYTHONPATH=src python3 -m story_video.cli voice-preview story.json --voice-gender male --force
PYTHONPATH=src python3 -m story_video.cli voice story.json --force
PYTHONPATH=src python3 -m story_video.cli pace story.json --force
PYTHONPATH=src python3 -m story_video.cli render story.json --force
```
