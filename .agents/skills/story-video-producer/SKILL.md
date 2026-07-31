---
name: story-video-producer
description: Production executor skill. Takes session.json and script.md produced by upstream skills, compiles the story.json manifest, generates scene images using the agent's native image tool, generates narration audio via the configured TTS provider, and renders the final MP4 video. Run after interview-story-config and content-creator have both completed.
---

# Story Video Producer

This skill is the **production executor**. It does not ask questions, search the web, or generate story ideas. It takes what upstream skills produced and turns it into a finished video. Every step has a clearly defined input and output.

---

## Prerequisites

Confirm these files exist before starting. If either is missing, stop and direct the user to run the appropriate upstream skill first.

| File | Produced By | If Missing |
|---|---|---|
| `library/<project_slug>/session.json` | `interview-story-config` | Run that skill first |
| `library/<project_slug>/script.md` | `content-creator` | Run that skill first |

Read `session.json` fully before starting. Extract `project_slug` from the `session.project_slug` field — all paths in this skill are relative to `library/<project_slug>/`.

---

## Step 1 — Compile `story.json`

The rendering engine only understands `story.json` — the manifest format. Your first job is to translate `session.json` + `script.md` into this format.

### How to read `script.md`
Each scene in `script.md` follows this structure:
```markdown
## Scene N
**Narration:**
<narration text>

**Image Direction:**
<one-line visual description>
```

Extract these two fields for every scene.

### How to build `story.json`
Construct the manifest from the extracted fields and `session.json` values:

```json
{
  "project": {
    "title": "<session.json: brief.topic>",
    "language": "<session.json: brief.language>",
    "aspect_ratio": "<session.json: video.aspect_ratio>",
    "resolution": "<session.json: video.resolution>",
    "fps": "<session.json: video.fps>"
  },
  "voice": {
    "provider": "<session.json: voice.provider>",
    "model": "<session.json: voice.model>",
    "voice": "<session.json: voice.voice>",
    "response_format": "wav"
  },
  "scenes": [
    {
      "id": "scene-001",
      "narration": "<narration text from script.md Scene 1>",
      "image_prompt": "<image direction from script.md Scene 1>",
      "image_path": "images/scene-001.png",
      "audio_path": null
    }
  ]
}
```

Scene IDs must be zero-padded three digits: `scene-001`, `scene-002`, etc.
Image paths must be relative: `images/scene-NNN.png` (not absolute paths).

Write the compiled manifest to:
```
library/<project_slug>/story.json
```

---

## Step 2 — Generate Scene Images

For each scene, generate one image using the **agent's native `generate_image` tool**. This is an internal Antigravity capability — there is no external image provider or CLI command for this step.

### Image generation rules

1. **One image per scene.** Do not batch or combine scenes.
2. **Use the scene's `image_prompt`** from `story.json` as the base prompt.
3. **Prepend the global visual style** from `session.json: visual.style` to every prompt to ensure consistency across all scenes. Example:
   ```
   "premium cinematic digital painting, warm golden hour lighting — <scene image_prompt>"
   ```
4. **Aspect ratio** must match `session.json: video.aspect_ratio`. Pass `16:9` or `9:16` to the image tool accordingly.
5. **Save path**: Save each image to:
   ```
   library/<project_slug>/images/scene-001.png
   library/<project_slug>/images/scene-002.png
   ...
   ```
   Create the `images/` folder if it does not exist.
6. **Update `story.json`** after saving each image — confirm the `image_path` field for that scene points to the saved file.

Do not proceed to audio generation until all scene images are saved and paths are confirmed in `story.json`.

---

## Step 3 — Generate Narration Audio

Run the CLI voice command against the compiled manifest:

```bash
PYTHONPATH=src python3 -m story_video.cli voice library/<project_slug>/story.json
```

This command reads the `voice` block from `story.json`, calls the configured TTS provider (e.g. `gemini_tts`) for each scene's narration text, and saves audio files to:
```
library/<project_slug>/audio/scene-001.wav
library/<project_slug>/audio/scene-002.wav
...
```

The command automatically reads the API key from `~/.config/story-video-maker/.env` via the project's built-in key loader — no manual key passing required.

If audio generation fails for any scene, diagnose the error before retrying. Common causes: missing API key, network timeout, malformed narration text.

---

## Step 4 — Pace Narration (Optional)

If the user requested a specific pacing (e.g. cinematic slowdown), run:

```bash
PYTHONPATH=src python3 -m story_video.cli pace library/<project_slug>/story.json --factor 0.92
```

Pacing factors: `0.85` (slow/cinematic) · `0.92` (slightly relaxed) · `1.0` (natural speed, skip this step).

---

## Step 5 — Render Final Video

Run the render command:

```bash
PYTHONPATH=src python3 -m story_video.cli render library/<project_slug>/story.json
```

The renderer reads the manifest, processes each scene with Ken Burns motion and crossfade transitions, burns subtitles if enabled, mixes background music if configured, and writes the final output to:
```
library/<project_slug>/output/final-video.mp4
```

Verify the output exists and is a valid video file after the command completes.

---

## Step 6 — Update Status

After successful render, update `session.json`:
- Set `session.status` to `"done"`
- Set `session.completed_at` to the current ISO timestamp

---

## Hard Rules

- **No image generation via CLI or external scripts.** Images are generated exclusively using the agent's native `generate_image` tool.
- **Compile `story.json` before any other step.** The CLI commands all depend on a valid manifest.
- **Scene IDs must be sequential and zero-padded** (`scene-001`, not `scene-1` or `1`).
- **Image paths in `story.json` must be relative**, not absolute. The CLI resolves them against the project folder.
- **Never overwrite existing output without user confirmation.** If `final-video.mp4` already exists, ask before re-rendering.

---

## Reference Files

For the full `story.json` schema and field definitions, read:
[story-schema.md](file:///Users/aryaveer/Projects/story-video-maker/.agents/skills/story-video-producer/references/story-schema.md)
