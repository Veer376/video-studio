---
name: intake
description: Pre-flight brief gathering skill. Run this at the start of any video project. Gathers intent, tone, language, voice, aspect ratio, and pacing to create session.json.
---

# Intake Skill

Run this skill at the very beginning of every new video project, before writing any script or generating any assets. The output is a `session.json` file that acts as the single source of truth for the entire video production pipeline.

---

## When to Activate

Activate this skill when:
- The user says they want to create a new story video.
- No `session.json` exists in the target project folder.
- The user says "let's start fresh" or "new video".

> [!NOTE]
> Use the `/grill-me` or `interview-me` skill, if available in your system.
Do **not** re-run this if a `session.json` already exists and `status` is not `intake_complete` — resume from where the pipeline left off instead.

---

## Intake Workflow

Conduct the intake as a natural, friendly conversation. Acknowledge each answer before moving to the next group.

### Group 1 — The Idea
> **Q1.** What is this video about? Give me the core idea — it can be a theme, a story concept, a life lesson, a character, or even just a feeling.
> **Q2.** What tone should it have? *(warm storytelling / motivational / devotional / educational / poetic — or describe it in your own words)*
> **Q3.** Who is the audience? *(general adults / children / spiritual seekers / students — or describe)*

### Group 2 — The Format
> **Q4.** How long should the video be? *(e.g., 30 seconds, 1 minute, 2 minutes, 4 minutes)*
> **Q5.** Horizontal (16:9, for YouTube) or Vertical (9:16, for Reels/Shorts)?

### Group 3 — Language & Voice
> **Q7.** What language? *(Hindi / English / Hinglish)*
> **Q8.** Which voice style?
> - `Puck` — expressive, male (Gemini TTS, recommended)
> - `Aoede` — warm, female (Gemini TTS)

### Group 4 — Visual Style (Optional)
> **Q9.** Any specific visual style? *(e.g., ancient India, modern urban, nature documentary, abstract watercolour)* — or press Enter to use the cinematic digital painting default.

---

## Derived Values

After the intake, derive this value automatically — do **not** ask the user:

```
project_slug       = YYYY-MM-DD_<kebab-title-from-topic>
```

---

## Output

Follow these steps in exact order:

1. **Derive the `project_slug`** from the topic: lowercase, spaces replaced with hyphens, prefixed with today's date. Example: `2026-08-01_krishna-motivation`.
2. **Create the project folder** if it does not already exist:
   ```
   library/<project_slug>/
   ```
3. **Write `session.json`** inside that folder:
   ```
   library/<project_slug>/session.json
   ```
   Set `status: "intake_complete"` in the output.

### `session.json` Schema:
```json
{
  "session": {
    "created_at": "2026-08-01T12:30:00",
    "project_slug": "2026-08-01_krishna-motivation",
    "status": "intake_complete"
  },
  "brief": {
    "topic": "Motivational story of Lord Krishna offering life wisdom",
    "theme": "motivation",
    "tone": "motivational",
    "language": "hi-IN",
    "audience": "general adults"
  },
  "video": {
    "target_duration_seconds": 240,
    "aspect_ratio": "16:9",
    "resolution": "1920x1080",
    "fps": 30,
    "subtitles_enabled": true
  },
  "voice": {
    "provider": "gemini_tts",
    "model": "gemini-3.1-flash-tts-preview",
    "voice": "Puck",
    "language": "hi-IN"
  },
  "visual": {
    "style": "premium cinematic digital painting, vivid colors, mystical lighting, ancient India"
  }
}
```

4. **Confirm to the user** with a 3-line summary of the creative brief.

---

## Hard Rules

- Default voice if skipped: `Aoede` (gemini_tts).
- Default aspect ratio if skipped: `16:9`.
- Default language if skipped: `hi-IN`.
- Never generate story content, images, or audio during this skill. This skill only asks questions and writes `session.json`.
