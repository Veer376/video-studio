---
name: interview-story-config
description: Pre-flight questionnaire skill. Run this before creating any story video. Asks the user structured questions about their creative intent, pacing, language, voice, and visual preferences, then outputs a session.json config file that feeds all downstream skills (content-creator, create-story-video).
---

# Interview Story Config

Run this skill at the very beginning of every new video project, before writing any story content or generating any assets. The output is a `session.json` file that acts as the single source of truth for the entire video production pipeline.

---

## When to Activate

Activate this skill when:
- The user says they want to create a new story video.
- No `session.json` exists in the target project folder.
- The user says "let's start fresh" or "new video".

> [!IMPORTANT]
> When this skill is activated, the agent MUST immediately ask the user to run the `/grill-me` slash command to start the interactive onboarding interview. Do not ask interview questions manually; rely on the `/grill-me` flow.

Do **not** re-run this if a `session.json` already exists and `status` is not `interview_complete` — resume from where the pipeline left off instead.

---

## Interview Workflow

> [!TIP]
> Recommend that the user invokes the `/grill-me` slash command to run this pre-flight questionnaire. This triggers a structured, interactive Q&A modal that makes the onboarding process seamless.

Conduct the interview as a natural, friendly conversation — not a form. Ask one or two questions at a time, not all at once. Acknowledge each answer before moving to the next group.

### Group 1 — The Idea
Ask these first. This is the creative heart of the interview.

> **Q1.** What is this video about? Give me the core idea — it can be a theme, a story concept, a life lesson, a character, or even just a feeling.

> **Q2.** What tone should it have? *(warm storytelling / motivational / devotional / educational / poetic — or describe it in your own words)*

> **Q3.** Who is the audience? *(general adults / children / spiritual seekers / students — or describe)*

### Group 2 — The Format
Ask these after Group 1 is clear.

> **Q4.** How long should the video be? *(e.g., 30 seconds, 1 minute, 2 minutes)*

> **Q5.** Do you want fast cuts or a cinematic slow pace?
> - **Fast**: 1 image every ~5 seconds (punchy, dynamic)
> - **Standard**: 1 image every ~10 seconds (balanced)
> - **Cinematic**: 1 image every ~12–15 seconds (slow, immersive)

> **Q6.** Horizontal (16:9, for YouTube) or Vertical (9:16, for Reels/Shorts)?

### Group 3 — Language & Voice
> **Q7.** What language? *(Hindi / English / Hinglish)*

> **Q8.** Which voice style?
> - `Aoede` — warm, female (Gemini TTS, recommended)
> - `Puck` — expressive, male (Gemini TTS)
> - `priya` — natural female Hindi (Sarvam TTS)
> - `gokul` — natural male Hindi (Sarvam TTS)

### Group 4 — Visual Style (Optional)
Only ask this if the user has not described visual preferences elsewhere. If they say "skip" or "default", use the standard cinematic style.

> **Q9.** Any specific visual style? *(e.g., ancient India, modern urban, nature documentary, abstract watercolour)* — or press Enter to use the cinematic digital painting default.

---

## Derived Values

After the interview, derive these values automatically — do **not** ask the user:

```
target_scene_count = round(target_duration_seconds / seconds_per_scene)
project_slug       = YYYY-MM-DD_<kebab-title-from-topic>
```

The `seconds_per_scene` mapping:
- Fast → 5
- Standard → 10
- Cinematic → 12

---

## Output

Follow these steps in exact order:

1. **Derive the `project_slug`** from the topic: lowercase, spaces replaced with hyphens, prefixed with today's date. Example: `2026-07-31_aarav-ka-sapna`.

2. **Create the project folder** if it does not already exist:
   ```
   library/<project_slug>/
   ```
   This is the root of everything for this video. All subsequent skills write into this folder.

3. **Write `session.json`** inside that folder:
   ```
   library/<project_slug>/session.json
   ```
   Follow the exact schema defined in [session-config-schema.md](file:///Users/aryaveer/Projects/story-video-maker/.agents/skills/interview-story-config/references/session-config-schema.md).
   Set `status: "interview_complete"` in the output.

4. **Confirm to the user** with a 3-line summary of the creative brief:
   > "Got it. Here's your creative brief — [summarise in 3 lines]. Ready to generate story templates?"

---

## Hard Rules

- Never skip Group 1 (the idea). All other groups have sensible defaults.
- Default voice if skipped: `Aoede` (gemini_tts).
- Default pacing if skipped: `cinematic` (12s per scene).
- Default aspect ratio if skipped: `16:9`.
- Default language if skipped: `hi-IN`.
- Never generate story content, images, or audio during this skill. This skill only asks questions and writes `session.json`.
