---
name: render
description: Production executor skill. Reads session.json, scenes.json, audio/narration.wav, audio/timestamps.json and scene images to assemble the final MP4 video. Runs after illustrate.
---

# Render Skill

This skill is the **film editor**. It takes all assets — one audio track, N images, Groq word timestamps, scene timing — and assembles the final MP4 using FFmpeg.

---

## When to Activate

Activate this skill when:
- `session.json` status is `"illustrate_complete"`
- `scenes.json` has `start_time`, `end_time`, `image_path` all non-null for every scene
- `audio/narration.wav` exists
- `audio/timestamps.json` exists

---

## Pipeline (3 stages, run in order)

```
Stage 1 — render_subtitles.py  →  subtitles/story.ass
Stage 2 — render_video.py      →  temp/video-no-audio.mp4
Stage 3 — render_final.py      →  output/final-video.mp4
```

---

## Stage 1 — Generate Subtitles

```bash
python3 .agents/skills/render/scripts/render_subtitles.py \
  --project-dir library/<project_slug>
```

**What it does:**
- Reads every word from `audio/timestamps.json` (Groq word-level output)
- Groups words by scene using `scenes.json` `start_time` / `end_time`
- For each scene, builds cumulative word-reveal subtitle lines:
  - Each word becomes a new ASS `Dialogue` entry that shows all words up to and including the current word
  - Start time = this word's Groq `start`, End time = next word's Groq `start` (or scene `end_time`)
- Outputs `subtitles/story.ass` — a single ASS file with exact Groq timings

> [!NOTE]
> ASS (Advanced SubStation Alpha) format is used instead of PNG overlays because it:
> - Uses exact Groq word timings (not estimated)
> - Produces one file instead of hundreds of PNGs
> - Renders natively via FFmpeg `ass` filter
> - Supports rich Devanagari styling (font, size, outline, position)

---

## Stage 2 — Render Video (Ken Burns + Crossfades + Subtitles)

```bash
python3 .agents/skills/render/scripts/render_video.py \
  --project-dir library/<project_slug>
```

**What it does internally (3 sub-stages):**

**Sub-stage A — Render each scene clip:**
For each scene in `scenes.json`:
- Duration = `end_time - start_time`
- Applies Ken Burns slow zoom to the scene's image
- Resolution and FPS from `session.json`
- Output: `temp/scenes/scene-NNN.mp4` (silent, no audio)

**Sub-stage B — Concatenate scenes with crossfades:**
- Joins all scene clips using FFmpeg `xfade=transition=fade:duration=0.4` between each pair
- Output: `temp/concat-video.mp4`

**Sub-stage C — Burn ASS subtitles:**
- Applies `subtitles/story.ass` via FFmpeg `ass` filter
- Output: `temp/video-no-audio.mp4`

---

## Stage 3 — Final Mux (Video + Audio)

```bash
python3 .agents/skills/render/scripts/render_final.py \
  --project-dir library/<project_slug>
```

**What it does:**
- Takes `temp/video-no-audio.mp4` + `audio/narration.wav`
- Muxes into final MP4 with AAC audio at 192k
- Uses `-shortest` to ensure audio and video end together
- Output: `output/final-video.mp4`

---

## Output File

```
library/<project_slug>/output/final-video.mp4
```

---

## Update Status

After all 3 stages complete:
- Update `session.json` → `status: "render_complete"`

---

## Hard Rules

- **Never re-encode unnecessarily:** Stage 3 copies the video stream (`-c:v copy`) if subtitles are already burned in.
- **Scene durations are authoritative from `scenes.json`**, not from script word counts or estimates.
- **ASS subtitle timing is authoritative from `timestamps.json`** — never estimate subtitle timing.
- **Do not modify `scenes.json` or `timestamps.json` during render.** Read-only.
