# Story Video Maker — Development Todo List

This is the central task tracker for the story video maker studio, located in the project's `todo/` directory.

---

## 1. Gemini-Optimized Script Generation
*Goal: Leverage Gemini's native inline vocal tags for high-end narration prosody.*

- [ ] **Create Scripting Skill**: Add a dedicated skill file (or update `content-creator`) specifically detailing how to write scripts optimized for Gemini's inline tags (`[medium pause]`, `[long pause]`, `[excitedly]`, `[whispers]`, `[sadly]`).
- [ ] **Auto-Wrap API Payload**: Update `_call_gemini_tts` in `audio.py` to automatically prepend the "Director's Notes" instruction block if not already present in the script text, ensuring Gemini executes the bracket directions instead of speaking them.

---

## 2. Word-by-Word Subtitle Rendering
*Goal: Animate subtitles word-by-word matching the speaker cadence (as verified in test_subtitle_render.py).*

- [ ] **Timing-Calculated Subtitles**: Replace the static full-scene subtitle PNG overlay with cumulative word-by-word subtitle clips, using the audio duration and a timing speed constant (e.g. `0.93` speed factor).
- [ ] **Layout Margins**: Bake the horizontal (`MARGIN_H_PERCENT`) and vertical padding options directly into the rendering configuration.

---

## 3. Interview Interactive Command
*Goal: Integrate the `/grill-me` workflow for a smoother user experience.*

- [ ] **Interactive Onboarding**: Update the `interview-story-config` skill to explicitly guide the user to run the `/grill-me` slash command so the initial onboarding is fully interactive.
