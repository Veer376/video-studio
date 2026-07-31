# Story Video Maker — Development Todo List

This is the central task tracker for the story video maker studio, located in the project's `todo/` directory.

---

## 1. Gemini-Optimized Script Generation
*Goal: Leverage Gemini's native inline vocal tags for high-end narration prosody.*

- [ ] **Create Scripting Skill**: Add a dedicated skill file (or update `content-creator`) specifically detailing how to write scripts optimized for Gemini's inline tags (`[medium pause]`, `[long pause]`, `[excitedly]`, `[whispers]`, `[sadly]`).
- [ ] **Auto-Wrap API Payload**: Update `_call_gemini_tts` in `src/audio/gemini.py` to automatically prepend the "Director's Notes" instruction block if not already present in the script text, ensuring Gemini executes the bracket directions instead of speaking them.

---

## 2. Word-by-Word Subtitle Rendering (Completed)
*Goal: Animate subtitles word-by-word with fade-in, matching the speaker cadence.*

- [x] **Timing-Calculated Subtitles**: Replace the static full-scene subtitle PNG overlay with cumulative word-by-word subtitle clips.
- [x] **Layout Margins**: Bake the horizontal (`MARGIN_H_PERCENT`) and vertical padding options directly into the rendering configuration.
- [x] **Fade-In Animation**: Added PIL Image blend transition mapping over `0.1s` fade durations to smoothly introduce new words without causing flicker or jumping.

---

## 3. Flat Directory Structure Refactoring (Completed)
*Goal: Remove nested 'generated' folders and flatten the source layout.*

- [x] **Flatten Library Directory**: Shifted paths so that `images/`, `audio/`, `scenes/`, `subtitles/`, `temp/`, and `output/` sit directly under `library/<slug>/`.
- [x] **Project Src Flattening**: Moved everything from `src/story_video/` directly into `src/` to remove nesting.
- [x] **Provider-Specific Audio Packages**: Segmented `audio.py` into `base.py`, `gemini.py`, `sarvam.py`, and `groq.py` under the `src/audio/` package.

---

## 4. Interview Interactive Onboarding (Completed)
*Goal: Integrate the `/grill-me` workflow for a smoother user experience.*

- [x] **Interactive Onboarding**: Updated the `interview-story-config` skill to explicitly guide the agent to ask the user to run the `/grill-me` slash command so the onboarding is fully interactive.

---

## 5. Future Improvement Areas

### 1. TTS Rate Limiting & Quota Crashing (High Priority)
* Add a configurable sleep delay (e.g., `time.sleep(20)` between requests) inside `src/audio/base.py` for Gemini free tier keys.
* Implement an automatic retry mechanism with exponential backoff when encountering HTTP 429.

### 2. Multi-Model Voice Inconsistency
* The CLI should support a fallback list of models.
* Offer to automatically regenerate the earlier scenes under a fallback model to guarantee vocal uniformity if a model switch happens mid-project.

### 3. Lack of Image Generation Automation
* Add support for the Gemini Imagen API inside the Python engine so that scene visual assets can be generated command-line end-to-end.