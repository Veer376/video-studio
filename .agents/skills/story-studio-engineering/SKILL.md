---
name: story-studio-engineering
description: Engineering handbook for the story video studio codebase. Use when modifying the rendering pipeline, adding new TTS providers, writing tests, debugging media issues, or managing project architecture and dependencies.
---

# Story Studio Engineering

Use this skill when developing, refactoring, or extending the `story-video-maker` rendering codebase. It ensures high code quality, clean architecture, automated testing, and proper version control.

---

## 1. API Key Management

API keys are **never** hardcoded in source files and **never** committed to git. This project uses a namespaced XDG config file that is automatically loaded at import time via `_load_env_keys()` in `audio.py`.

### Location (required)
```
~/.config/story-video-maker/.env
```

### Format
```env
# story-video-maker API keys
GEMINI_API_KEY="your_key_here"
SARVAM_API_KEY="your_key_here"
GROQ_API_KEY="your_key_here"
```

### Rules
- This file lives **outside the project repository** so it is physically impossible to commit it to git.
- The project root `.env` (gitignored) can be used as a local per-session override for development, but should never be the primary location.
- The loader uses a **first-match wins, never overwrite** policy. A key already present in `os.environ` (e.g., set by CI/CD) is never clobbered.
- When adding a new API provider, add its key variable to this section and document its name here.

---


Always preserve the separation of concerns within the `src/` directory. Never combine media rendering logic with API callers or CLI argument parsing:

* **[models.py](file:///Users/aryaveer/Projects/story-video-maker/src/models.py)**: Dataclasses mapping to `story.json` schema. Keep parsing rules here.
* **[manifest.py](file:///Users/aryaveer/Projects/story-video-maker/src/manifest.py)**: Manifest file loaders, savers, and file path validators.
* **[audio/](file:///Users/aryaveer/Projects/story-video-maker/src/audio)**: Package that handles all external TTS integrations (Gemini, Sarvam, Groq) and raw PCM conversions.
* **[images.py](file:///Users/aryaveer/Projects/story-video-maker/src/images.py)**: Core image handling and aspect ratio validation.
* **[subtitles.py](file:///Users/aryaveer/Projects/story-video-maker/src/subtitles.py)**: SRT generator and subtitles burner overlays.
* **[renderer.py](file:///Users/aryaveer/Projects/story-video-maker/src/renderer.py)**: Main FFmpeg composition logic (Ken Burns pan/zoom, audio mixing, concatenation).
* **[ffmpeg.py](file:///Users/aryaveer/Projects/story-video-maker/src/ffmpeg.py)**: Low-level shell wrappers executing `ffmpeg` and `ffprobe` subprocesses.
* **[cli.py](file:///Users/aryaveer/Projects/story-video-maker/src/cli.py)**: Argument parsing entry point. Avoid putting business logic here.

---

## 2. Testing Guidelines (Non-negotiable)

Any modification, bug fix, or feature addition must include tests to ensure the pipeline remains stable.
* **Run the test suite** before making any commit:
  ```bash
  PYTHONPATH=src python3 -m unittest discover -s tests
  ```
* **Adding Tests**: Place new test modules in the `tests/` directory following the naming pattern `test_*.py`.
* **Mock External Calls**: Never make real network requests to external APIs (Gemini, Sarvam, Groq) during test runs. Use `unittest.mock` to mock `urllib.request.urlopen` and return simulated responses.
* **Test Validation**: Ensure test outputs check for exact data formats (e.g. Wav mono, PCM format, exact parsed manifest values).

---

## 3. Git Workflow & Version Control

Maintain clean, atomic development history using git:
* **Commits**: Every feature addition, bug fix, or documentation change must be committed to git.
* **Commit Message Standard**: Use clear, descriptive, imperative commit messages (e.g. `feat: add gemini_tts audio provider`, `fix: remove raw PCM byte swapping in gemini audio`).
* **Untracked Media**: Keep the `.gitignore` configuration updated so generated artifacts (inside `generated/` and `output/`) are never committed to the repository.

---

## 4. API Integration Contracts

When adding new service providers, follow these strict interfaces:

### TTS (Audio) Providers
1. Save audio to `generated/audio/<scene_id>.<ext>`.
2. All generated files **must** have standard container formats (WAV or MP3). 
3. If an API returns raw formats (like raw 16-bit PCM `audio/l16`), you must encapsulate the raw bytes in a standard WAV container using Python's built-in `wave` module before saving to disk.
4. Integrate with the `--voice-gender` option by mapping defaults in `set_voice_gender()`.

### Image Providers
1. Save images to `generated/images/<scene_id>.png`.
2. Validate width/height against project resolution (e.g. `1920x1080`).

---

## 5. Media Troubleshooting

* **Certificates**: On macOS, Python standard library URL requests often fail SSL verification. Always use the project's internal `_ssl_context()` helper, and fallback to `ssl._create_unverified_context()` on failure.
* **Bitrates & Probing**: Always check that audio assets can be successfully read by `ffprobe` using `ffmpeg.probe_duration()` before pacing or rendering.
