---
name: create-image-story
description: Master entry point for Story Video Maker's image-story workflow. Read this skill first for any image-based story creation task. Defines the full pipeline, maps all available skills in sequence, documents agent capabilities, and provides resume logic for interrupted runs.
---

# Story Video Maker — Master Pipeline

This is the **entry point skill**. Read this before invoking any other skill. It maps the entire system and tells you exactly what to do, in what order, for any image-based story creation task.

---

## What This Project Is

Story Video Maker is an AI-powered pipeline for creating **cinematic narrative short videos** — primarily Hindi-language motivational and spiritual storytelling. A finished video consists of:

- Researched, emotionally resonant story narration (`research.md`)
- A single clean script with storytelling optimization (`script.md`)
- An in-place stateful scenes mapping (`scenes.json`)
- Continuous TTS-synthesised Hindi narration audio (`audio/narration.wav`)
- Precise word-level timing offsets extracted from Groq Whisper (`audio/timestamps.json`)
- High-quality landscape images generated via Cloudflare Workers AI (`images/`)
- ffmpeg-rendered MP4 with jitter-free Ken Burns motion, crossfade transitions, and word-by-word subtitle overlays (`output/final-video.mp4`)

The pipeline is **fully stateful**: every video lives in its own folder inside `library/` and can be paused and resumed at any step.

## Naming Contract

- `Story Video Maker`: product/repository name.
- `create-image-story`: this master skill for the complete creative + production workflow.
- `run-pipeline`: production-only skill.
- `story-video`: project CLI executable.
- `image-story`: current image-based production pipeline.

---

## Skills Map

Six pipeline skills exist in `.agents/skills/`. Creative skills write source files; `run-pipeline` calls the project-owned production pipeline.

| Skill | Role | Reads | Writes |
|---|---|---|---|
| `intake` | Onboarding creative brief — gathers user's intent | User answers | `library/<project_name>/session.json` |
| `research` | Content discovery — searches web for facts, shlokas, quotes and stories | `session.json` | `library/<project_name>/research.md` |
| `compose` | Script generation — writes the story in spoken prose rhythm | `research.md` | `library/<project_name>/script.md` |
| `split-script` | Scene splitting — divides the narration into scenes at natural boundaries, writes the lean `scenes.json` skeleton (text only) | `script.md` | `library/<project_name>/scenes.json` (skeleton) |
| `orchestrate-visuals` | Visual concept design — builds character visual identity sheets from the story, fills `image_prompt` for every scene with consistent, cinematically-aware descriptions | `scenes.json` (skeleton), `script.md` | updates `scenes.json` (fills `image_prompt`) |
| `run-pipeline` | Production execution — resumes voice, Cloudflare image generation, and render through `story-video` CLI | `session.json`, `script.md`, `scenes.json` | `audio/`, `images/`, `subtitles/`, `temp/`, `output/final-video.mp4` |

---

## Project Folder Structure

Every video lives in its own named folder inside `library/`:

```
story-video-maker/
├── library/
│   └── <project_name>/                   ← one folder per video
│       ├── session.json                   ← creative brief + pipeline status
│       ├── research.md                    ← discovered real stories and sources
│       ├── script.md                      ← approved narration prose
│       ├── scenes.json                    ← stateful scene timing and assets manifest
│       ├── audio/
│       │   ├── narration.wav              ← single continuous narration audio
│       │   └── timestamps.json            ← raw Groq Whisper word-level timestamps
│       ├── images/
│       │   ├── scene-001.png
│       │   └── scene-002.png ...
│       └── output/
│           └── final-video.mp4            ← final rendered video
├── src/                                   ← rendering engine (Python utilities)
└── .agents/skills/                        ← all skill definitions
```

---

## The Full Pipeline (Resume Logic)

Before doing anything, check the file structures in `library/<project_name>/` and resume from the correct checkpoint:

```
Does library/<project_name>/session.json exist?
  No  → START at Skill: intake
  Yes → Does library/<project_name>/research.md exist?
          No  → START at Skill: research
          Yes → Does library/<project_name>/script.md exist?
                  No  → START at Skill: compose
                  Yes → Does library/<project_name>/scenes.json exist?
                          No  → START at Skill: split-script
                          Yes → Are all image_prompt fields in scenes.json null?
                                   Yes → START at Skill: orchestrate-visuals
                                   No  → Does library/<project_name>/audio/narration.wav exist?
                                          No  → START at Skill: run-pipeline
                                          Yes → Do all images in library/<project_name>/images/ exist?
                                                  No  → START at Skill: run-pipeline
                                                  Yes → Does library/<project_name>/output/final-video.mp4 exist and probe correctly?
                                                          No  → START at Skill: run-pipeline
                                                          Yes → DONE — confirm with user
```

For production stages, prefer the project CLI:

```bash
story-video status library/<project_name>
story-video run library/<project_name>
story-video pipeline image-story library/<project_name>
story-video stage illustrate library/<project_name>
story-video stage illustrate library/<project_name> --force
```

---

## API Credentials

Exposes credentials loaded from `~/.config/projects/.env` (outside the repository):
- `GEMINI_API_KEY`: Audio generation (TTS)
- `TAVILY_API_KEY`: Script research queries
- `GROQ_API_KEY`: Transcription & word timestamp alignment
- `CLOUDFLARE_ACCOUNT_ID` & `CLOUDFLARE_API_TOKEN`: Cloudflare Workers AI Flux image generation

---

## Hard Rules

1. **Always read this skill first** before any video creation task.
2. **Never skip ahead** — the progressive status gates downstream generation (e.g. do not illustate before timings are aligned).
3. **No story writing or image generation in intake or research.** Decouple formatting from production.
4. **All timings must be floats.** Never cast timestamps to integers in the manifests.
5. **Commit the final video folder:** Once rendering completes and the user approves, run `git add library/<project_name>/ && git commit -m "feat: complete video <project_name>"` (media is ignored automatically).
6. **Do not run production code from skill folders.** Voice, illustration, and render execution lives under `src/studio/` and is invoked through `story-video`.
