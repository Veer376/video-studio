# Story Video Maker — Development Todo List

This is the central task tracker for the story video maker studio, located in the project's `todo/` directory.

---

## 1. Gemini-Optimized Script Generation
*Goal: Leverage Gemini's native inline vocal tags for high-end narration prosody.*

- [ ] **Create Scripting Skill**: Add a dedicated skill file (or update `content-creator`) specifically detailing how to write scripts optimized for Gemini's inline tags (`[medium pause]`, `[long pause]`, `[excitedly]`, `[whispers]`, `[sadly]`).
- [ ] **Auto-Wrap API Payload**: Update `_call_gemini_tts` in `audio.py` to automatically prepend the "Director's Notes" instruction block if not already present in the script text, ensuring Gemini executes the bracket directions instead of speaking them.

---

- [x] **Timing-Calculated Subtitles**: Replace the static full-scene subtitle PNG overlay with cumulative word-by-word subtitle clips, using the audio duration and a timing speed constant (e.g. `0.93` speed factor).
- [x] **Layout Margins**: Bake the horizontal (`MARGIN_H_PERCENT`) and vertical padding options directly into the rendering configuration.

---

## 3. Flat Directory Structure Refactoring
*Goal: Remove nested 'generated' folders from the project library.*

- [x] **Flatten Library Directory**: Shifted paths so that `images/`, `audio/`, `scenes/`, `subtitles/`, `temp/`, and `output/` sit directly under `library/<slug>/`.
- [x] **Project Src Flattening**: Moved everything from `src/story_video/` directly into `src/` to remove nesting from the Python source package.
- [x] **Test Updates**: Restructured unit tests to use flat imports (`import ffmpeg`, `from audio import...`) and adjusted mock paths.

---

## 4. Interview Interactive Onboarding
*Goal: Integrate the `/grill-me` workflow for a smoother user experience.*

- [ ] **Interactive Onboarding**: Update the `interview-story-config` skill to explicitly guide the user to run the `/grill-me` slash command so the initial onboarding is fully interactive.




Viewed config.yaml:1-12

Yes, during the execution of this project, I identified several **discrepancies and areas of friction** in the current story-video-maker pipeline. Here is a summary of these issues and how they can be corrected or improved:

---

### 1. TTS Rate Limiting & Quota Crashing (High Priority)
* **Discrepancy:** The `story-video voice` command loops through scenes sequentially and fires HTTP requests immediately. Because the Gemini API Free Tier has a rate limit of **3 requests/minute** and **10 requests/day**, a standard 5-scene video is guaranteed to hit the rate limit on the first run and crash the CLI.
* **Correction/Improvement:** 
  * Add a configurable sleep delay (e.g., `time.sleep(20)` between requests) inside `audio.py` for Free Tier keys.
  * Implement an automatic retry mechanism with exponential backoff when encountering `HTTP 429 (Resource Exhausted)` instead of raising a crash error immediately.

### 2. Multi-Model Voice Inconsistency
* **Discrepancy:** When we hit the daily quota on `gemini-3.1-flash-tts-preview` at scene 5, we manually switched the model in `story.json` to `gemini-2.5-flash-preview-tts` to finish generation. Although both models used the same voice configuration (`Puck`), mixing two different engine versions in the same video can cause subtle shifts in pronunciation, volume, or pitch between scenes.
* **Correction/Improvement:**
  * The CLI should support a fallback list of models in `config.yaml`.
  * If a fallback model is triggered mid-way, the CLI should prompt or automatically offer to regenerate the earlier scenes under the new model to guarantee vocal uniformity.

### 3. Missing Gitignore Safety for Library Media (Corrected)
* **Discrepancy:** The original `.gitignore` ignored the root `generated/` and `output/` folders, but did not ignore the `images/` directory inside `library/<project_slug>/`. Staging the library directory attempted to commit large generated PNG images.
* **Correction/Improvement:** I resolved this during the run by adding `library/*/images/` to the project's [.gitignore](file:///Users/aryaveer/Projects/story-video-maker/.gitignore). To make this robust, the project should also ignore `library/*/audio/` and any other binary formats in `library/` to keep the git index clean.

### 4. Lack of Image Generation Automation
* **Discrepancy:** There is no CLI script or provider integration for generating scene images. The pipeline relies entirely on the agent executing native tools to create the image, then manually copying and converting them.
* **Correction/Improvement:** 
  * Add support for the Gemini Imagen API inside the Python engine. 
  * This would allow running a single command like `PYTHONPATH=src python3 -m cli images library/<slug>/story.json` to generate all scene visual assets in one go, making the project truly runnable end-to-end without agent intervention.