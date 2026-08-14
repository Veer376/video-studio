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

Before asking questions, read `kathamind/config.json`. Use its non-empty `audience` value for `brief.audience`; do not ask the user for an audience. If the value is missing or invalid, report the configuration error instead of inventing a replacement.

**Short Format & Duration Coupling**: YouTube Shorts run up to 3 minutes (180 seconds) and require `9:16` vertical format.
- If the user requests a "Short", "vertical video", or specifies a duration `<= 180` seconds (e.g., 45s, 60s, 2–3 mins): automatically set `visual.aspect_ratio: "9:16"` and skip **Q3**. Still ask **Q4** because a YouTube Short may run anywhere up to 3 minutes and duration is a creative choice.
- If the user requests long-form or a duration `> 180` seconds (e.g., 5–12 mins): set `visual.aspect_ratio: "16:9"`.

### Group 1 — The Idea
> **Q1.** What is this video about? Give me the core idea — it can be a theme, a story concept, a life lesson, a character, or even just a feeling.
> **Q2.** What tone should it have? *(warm storytelling / motivational / devotional / educational / poetic — or describe it in your own words)*

### Group 2 — Format & Length
> **Q3.** What is the video format or aspect ratio? *(e.g., Short 9:16 (vertical Shorts, up to 3 min) / Long-form 16:9 (horizontal, 3+ min))*
> **Q4.** How long should the video be? *(e.g., 45 seconds, 90 seconds, or up to 3 minutes for a Short; 3–12 minutes for long-form)*

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
    "audience": "<from kathamind/config.json>",
    "target_duration_seconds": 600
  },
  "voice": {
    "language": "hi-IN"
  },
  "visual": {
    "aspect_ratio": "16:9"
  }
}
```

4. **Confirm to the user** with a 3-line summary of the creative brief.

---

## Hard Rules

- Always write `voice.language: "hi-IN"`; do not ask the user for language during intake.
- Aspect ratio defaults: If `target_duration_seconds <= 180` (or Short requested), `visual.aspect_ratio` MUST be `"9:16"`. If `target_duration_seconds > 180`, `visual.aspect_ratio` MUST be `"16:9"`.
- Never generate story content, images, or audio during this stage. This stage only asks questions and writes `session.json`.
