---
name: create-video
description: Master entry point for the Story Video Studio. Read this skill first for any video creation task. Defines the full pipeline, maps all available skills in sequence, documents agent capabilities, and provides resume logic for interrupted runs.
---

# Story Video Studio — Master Pipeline

This is the **entry point skill**. Read this before invoking any other skill. It maps the entire system and tells you exactly what to do, in what order, for any video creation task.

---

## What This Project Is

Story Video Studio is an AI-powered pipeline for creating **cinematic narrative short videos** — primarily Hindi-language motivational and spiritual storytelling. A finished video consists of:

- Researched, emotionally resonant story narration (`research.md`)
- A single clean script with storytelling optimization (`script.md`)
- An in-place stateful scenes mapping (`scenes.json`)
- Continuous TTS-synthesised Hindi narration audio (`audio/narration.wav`)
- Precise word-level timing offsets extracted from Groq Whisper (`audio/timestamps.json`)
- High-quality landscape images generated via Cloudflare Workers AI (`images/`)
- ffmpeg-rendered MP4 with jitter-free Ken Burns motion, crossfade transitions, and word-by-word subtitle overlays (`output/final-video.mp4`)

The pipeline is **fully stateful**: every video lives in its own folder inside `library/` and can be paused and resumed at any step.

---

## Skills Map

Eight verb-first skills exist in `.agents/skills/`. Each has a single, clear responsibility:

| Skill | Role | Reads | Writes |
|---|---|---|---|
| `intake` | Onboarding creative brief — gathers user's intent | User answers | `library/<slug>/session.json` |
| `research` | Content discovery — searches web for facts, shlokas, and stories | `session.json` | `library/<slug>/research.md` |
| `compose` | Script generation — writes the story in spoken prose rhythm | `research.md` | `library/<slug>/script.md` |
| `split-script` | Scene splitting — divides the narration into scenes at natural boundaries, writes the lean `scenes.json` skeleton (text + word_range only) | `script.md` | `library/<slug>/scenes.json` (skeleton) |
| `design-visuals` | Visual concept design — builds character visual identity sheets from the story, fills `image_prompt` for every scene with consistent, cinematically-aware descriptions | `scenes.json` (skeleton), `script.md` | updates `scenes.json` (fills `image_prompt`) |
| `voice` | Audio synthesis — generates continuous narration and extracts Groq timings | `script.md`, `scenes.json` | `audio/narration.wav`, `audio/timestamps.json`, updates `scenes.json` |
| `illustrate` | Image generation — batch requests images at matched aspect ratio | `scenes.json` | `images/`, updates `scenes.json` |
| `render` | Video rendering — bakes subtitles, zooms, crossfades, and muxes | `scenes.json`, `audio/` | `output/final-video.mp4` |

---

## Project Folder Structure

Every video lives in its own named folder inside `library/`:

```
story-video-maker/
├── library/
│   └── <YYYY-MM-DD_kebab-slug>/          ← one folder per video
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

Before doing anything, check the file structures in `library/<slug>/` and resume from the correct checkpoint:

```
Does library/<slug>/session.json exist?
  No  → START at Skill: intake
  Yes → Does library/<slug>/research.md exist?
          No  → START at Skill: research
          Yes → Does library/<slug>/script.md exist?
                  No  → START at Skill: compose
                  Yes → Does library/<slug>/scenes.json exist?
                          No  → START at Skill: split-script
                          Yes → Are all image_prompt fields in scenes.json null?
                                  Yes → START at Skill: design-visuals
                                  No  → Does library/<slug>/audio/narration.wav exist?
                                          No  → START at Skill: voice
                                          Yes → Do all images in library/<slug>/images/ exist?
                                                  No  → START at Skill: illustrate
                                                  Yes → Does library/<slug>/output/final-video.mp4 exist?
                                                          No  → START at Skill: render
                                                          Yes → DONE — confirm with user
```

---

## API Credentials

Exposes credentials loaded from `~/.config/story-video-maker/.env` (outside the repository):
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
5. **Commit the final video folder:** Once rendering completes and the user approves, run `git add library/<slug>/ && git commit -m "feat: complete video <slug>"` (media is ignored automatically).
