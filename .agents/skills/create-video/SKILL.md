---
name: create-video
description: Master entry point for the Story Video Studio. Read this skill first for any video creation task. Defines the full pipeline, maps all available skills in sequence, documents agent capabilities, and provides resume logic for interrupted runs.
---

# Story Video Studio — Master Pipeline

This is the **entry point skill**. Read this before invoking any other skill. It maps the entire system and tells you exactly what to do, in what order, for any video creation task.

---

## What This Project Is

Story Video Studio is an AI-powered pipeline for creating **cinematic narrative short videos** — primarily Hindi-language motivational and spiritual storytelling. A finished video consists of:

- Researched, emotionally resonant story narration
- AI-generated scene images with consistent visual style
- TTS-synthesised Hindi narration (Gemini TTS)
- ffmpeg-rendered MP4 with Ken Burns motion, crossfade transitions, and subtitle overlays

The pipeline is **fully stateful**: every video lives in its own folder inside `library/` and can be paused and resumed at any step.

---

**Image generation note:** Use the agent's native image generation tool or skill exclusively. There is no CLI command or external script for image generation in this project.

---

## Skills Map

Four skills exist in `.agents/skills/`. Each has a single, clear responsibility:

| Skill | Role | Reads | Writes |
|---|---|---|---|
| `interview-story-config` | Pre-flight questionnaire — understands the user's creative intent | User answers | `library/<slug>/session.json` |
| `content-creator` | Research + story generation — discovers real sources and writes narrative templates | `session.json` | `library/<slug>/research.md`, `library/<slug>/script.md` |
| `video-producer` | Production executor — compiles manifest, generates all assets, renders final video | `session.json`, `script.md` | `story.json`, `images/`, `audio/`, `output/final-video.mp4` |
| `story-studio-engineering` | Developer handbook — guides codebase changes, testing, and new provider integration | Source code | Source code |

Invoke `story-studio-engineering` only when modifying the Python codebase. For all video creation tasks, use the other three skills in order.

---

## Project Folder Structure

Every video lives in its own named folder inside `library/`:

```
story-video-maker/
├── library/
│   └── <YYYY-MM-DD_kebab-slug>/          ← one folder per video
│       ├── session.json                   ← creative brief + pipeline status
│       ├── research.md                    ← discovered real stories and sources
│       ├── script.md                      ← approved narration + image directions
│       ├── story.json                     ← compiled rendering manifest
│       ├── images/
│       │   ├── scene-001.png
│       │   └── scene-002.png ...
│       ├── audio/
│       │   ├── scene-001.wav
│       │   └── scene-002.wav ...
│       └── output/
│           └── final-video.mp4
├── src/                                   ← rendering engine (Python)
└── .agents/skills/                        ← all skill definitions
```

---

## The Full Pipeline

### How to Determine Where to Start (Resume Logic)

Before doing anything, check what already exists in `library/<slug>/`:

```
Does library/<slug>/session.json exist?
  No  → START at Step 1 (Interview)
  Yes → Does library/<slug>/script.md exist?
          No  → START at Step 2 (Content Discovery + Story Generation)
          Yes → Does library/<slug>/story.json exist?
                  No  → START at Step 3a (Compile Manifest)
                  Yes → Are all images in library/<slug>/images/ present?
                          No  → START at Step 3b (Image Generation)
                          Yes → Are all audio files in library/<slug>/audio/ present?
                                  No  → START at Step 3c (Audio Generation)
                                  Yes → Does library/<slug>/output/final-video.mp4 exist?
                                          No  → START at Step 3d (Render)
                                          Yes → DONE — confirm with user
```

This means you can safely re-invoke any skill and it will resume from the correct checkpoint without redoing completed work.

---

### Step 1 — Interview (Skill: `interview-story-config`)

**When:** No `session.json` exists yet.

Read and follow `.agents/skills/interview-story-config/SKILL.md`.

Outcome:
- `library/<slug>/` folder created
- `library/<slug>/session.json` written with `status: "interview_complete"`

---

### Step 2 — Content Discovery + Story Generation (Skill: `content-creator`)

**When:** `session.json` exists but `script.md` does not.

Read and follow `.agents/skills/content-creator/SKILL.md`.

This skill has two internal phases — run both before moving on:
- **Phase 1 (Discovery):** Search the web, write `research.md`
- **Phase 2 (Story Generation):** Generate 3–5 narrative templates → user picks one → write `script.md`

Do not proceed to Step 3 until the user has approved a template and `script.md` is written.

---

### Step 3 — Production (Skill: `video-producer`)

**When:** Both `session.json` and `script.md` exist.

Read and follow `.agents/skills/video-producer/SKILL.md`.

This skill runs four sub-steps in sequence:

**3a. Compile `story.json`**
Translate `session.json` + `script.md` into the manifest format the rendering engine understands. Write to `library/<slug>/story.json`.

**3b. Generate Scene Images**
For each scene in `story.json`, call `generate_image` with the scene's `image_prompt` prefixed with the global visual style from `session.json`. Save to `library/<slug>/images/scene-NNN.png`.

**3c. Generate Narration Audio**
```bash
PYTHONPATH=src python3 -m cli voice library/<slug>/story.json
```
The API key is loaded automatically from `~/.config/story-video-maker/.env`.

**3d. Render Final Video**
```bash
PYTHONPATH=src python3 -m cli render library/<slug>/story.json
```
Output: `library/<slug>/output/final-video.mp4`

Update `session.json` status to `"done"` after successful render.

---

## Key Configuration

### API Keys
Stored in `~/.config/story-video-maker/.env` (outside the repo, never committed):
```env
GEMINI_API_KEY="your_key_here"
SARVAM_API_KEY="your_key_here"
GROQ_API_KEY="your_key_here"
```
The project loads these automatically at import time via `_load_env_keys()` in `audio.py`.

### `session.json` Status Field
Track pipeline progress using `session.session.status`:

| Status | Meaning |
|---|---|
| `interview_complete` | session.json written, pipeline not started |
| `script_approved` | script.md written and approved by user |
| `rendering` | video-producer is actively running |
| `done` | final-video.mp4 exists and is verified |

---

## Hard Rules

1. **Always read this skill first** before any video creation task.
2. **Never generate images or audio before `script.md` is approved.** Content approval gates production.
3. **Never re-run the interview if `session.json` already exists** — resume from the checkpoint instead.
4. **Every completed video must be committed to git** — run `git add library/<slug>/ && git commit` after render. Keep generated media in `.gitignore`.
5. **Do not modify source code during a video creation run.** If a code bug is found, stop, fix it using `story-studio-engineering`, run tests, commit, then resume.
6. **Scene IDs in `story.json` must always be zero-padded three digits**: `scene-001`, not `scene-1`.

---

## What Is Still Needed (Roadmap)

The following improvements are planned but not yet built:

| Item | Status | Notes |
|---|---|---|
| Word-by-word subtitle rendering | 🔜 In progress | Test proven in brain/scratch; needs integration into `subtitles.py` |
| Custom `.svms` script format | ❌ Dropped | Natural text with ellipses + Gemini TTS context instruction achieves the same result |
| `library/` CLI integration | 🔜 Planned | CLI currently expects bare `story.json`; needs `library/<slug>/` path support |
| YouTube upload | ⏳ Later | Python YouTube Studio API integration |
| Orchestration agent | ⏳ Later | Single agent that chains all skills autonomously without manual invocation |
