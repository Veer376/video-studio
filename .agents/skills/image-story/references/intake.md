# Intake Stage

Run this stage at the beginning of a new video project, before writing a script or generating assets. Its output is the pipeline's `session.json` source of truth.

---

## When to Run

Run this stage when:
- The user says they want to create a new story video or a vertical Short.
- No `session.json` exists in the target project folder.
- The user says "let's start fresh", "new video", or "create a short".

> [!NOTE]
> Use the `ask_question` tool, if available in your system.
---

## Intake Workflow

Conduct the intake as a natural, friendly conversation. Acknowledge each answer before moving to the next group.

**Short Video Optimization**: If the user starts the conversation by requesting a "Short" or "vertical video", automatically set `visual.aspect_ratio` to `"9:16"` and skip **Q4**. Still ask **Q5** because a YouTube Short may run anywhere up to three minutes and duration is a creative choice.

### Group 1 — The Idea
> **Q1.** What is this video about? Give me the core idea — it can be a theme, a story concept, a life lesson, a character, or even just a feeling.
> **Q2.** What tone should it have? *(warm storytelling / motivational / devotional / educational / poetic — or describe it in your own words)*
> **Q3.** Who is the audience? *(general adults / children / spiritual seekers / students — or describe)*

### Group 2 — Format, Language & Length
> **Q4.** What is the video format or aspect ratio? *(e.g., Long-form 16:9 (recommended) / Short 9:16 (vertical Shorts))*
> **Q5.** How long should the video be? *(e.g., 45 seconds, 90 seconds, or up to 3 minutes for a Short; 10–12 minutes for long-form)*
> **Q6.** What language? *(Hindi / English / Hinglish)*

### Group 3 — Visual Style (Optional)
> **Q7.** Any specific visual style? *(e.g., ancient India, modern urban, nature documentary, abstract watercolour)* — or press Enter to use the cinematic digital painting default.

---

## Derived Values

After the intake, derive this value automatically — do **not** ask the user:

```
project_name       = <kebab-title-from-topic>
```

---

## Output

Follow these steps in exact order:

1. **Derive the `project_name`** from the topic: lowercase, spaces replaced with hyphens. Example: `krishna-motivation`.
2. **Create the project folder** if it does not already exist:
   ```
   library/<project_name>/
   ```
3. **Write `session.json`** inside that folder:
   ```
   library/<project_name>/session.json
   ```
   Set `status: "intake_complete"` in the output.

### `session.json` Schema:
```json
{
  "session": {
    "created_at": "2026-08-01T12:30:00",
    "project_name": "krishna-motivation",
    "status": "intake_complete"
  },
  "brief": {
    "topic": "Motivational story of Lord Krishna offering life wisdom",
    "tone": "motivational",
    "audience": "general adults",
    "target_duration_seconds": 600
  },
  "voice": {
    "language": "hi-IN"
  },
  "visual": {
    "style": "premium cinematic digital painting, vivid colors, mystical lighting, ancient India",
    "aspect_ratio": "16:9"
  }
}
```

4. **Confirm to the user** with a 3-line summary of the creative brief.

---

## Hard Rules

- Default language if skipped: `hi-IN`.
- Default aspect ratio if skipped: `16:9`. If vertical or Short is specified, set `visual.aspect_ratio` to `9:16`.
- The default production flow uses 30fps, Cloudflare images, Gemini TTS, and subtitles. Resolution matches the aspect ratio (`1920x1080` for `16:9`, `1080x1920` for `9:16`). Do not write those defaults into `session.json`.
- Keep `voice` lean for now: only write `voice.language`.
- Never generate story content, images, or audio during this stage. This stage only asks questions and writes `session.json`.
