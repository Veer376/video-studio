---
name: compose
description: Script-generation skill. Orchestrates the two-round process of blueprint presentation and script writing. Delegates narration craft rules to the hindi-voice-guide reference.
---

# Compose Skill

This skill is a **screenwriter and storyteller**. Its job is to translate raw research findings into an emotionally resonant narration script through a structured two-round process.

---

## When to Activate

Activate this skill when:
- `session.json` exists with `status: "research_complete"`
- `research.md` is written and available
- `script.md` does not yet exist, or the user wants to rewrite/regenerate the script

---

## Inputs

Read `library/<project_name>/session.json` before writing.

Treat `target_duration_seconds` as a rough script-length target, not a strict constraint.

> [!IMPORTANT]
> **Script Structure & Duration**
> Before generating blueprints or writing the script, check `target_duration_seconds` in `session.json`.
> If `target_duration_seconds` >= 480 seconds, you MUST read the long-form structural rules in `references/duration_rules/long.md`.

---

## Research Selection

Not all research belongs in the script. When selecting from `research.md`, apply this filter:
1. Does it serve the emotional arc?
2. Does it surprise the listener?
3. Does it deepen the core conflict?

If a fact is interesting but doesn't serve the story, cut it.

---

## Two-Round Process

### Round 1: Blueprint Presentation

Before writing the script, present **3 Titles, 1 Description, and 3 distinct Template Blueprints** to the user.

#### Title Strategies:
Generate 3 distinct titles:
1. **Curiosity Gap:** Intrigues the user to know something hidden.
2. **Emotional Conflict:** Focuses on the core human struggle.
3. **Direct Challenge:** Speaks directly to the viewer's current situation.

#### Description:
Write one 2–3 sentence description that summarizes the video's promise without spoiling the narrative turn. Include one emotional keyword and one curiosity trigger.

#### Template Blueprints:
Generate 3 distinct templates:
TEMPLATE — Macro Loop (0:00-0:15): <Hook + Anti-hook pair> Micro Loops: <Tension teasers at ~60s intervals> Middle arc: <How the story builds and connects to modern life — two sentences> Turn: <The emotional pivot or revelation — one sentence> Closing: <The final call to action or resolution — one sentence> Tone signature: <e.g., Rising inspiration, quiet contemplation, dramatic epic>

**Wait for the user's explicit selection before proceeding to Round 2.**

---

### Round 2: Script Writing

Once the user approves a title and template:

**Step 1 — Emotional Arc & Retention Anchors:**
Before writing, define the listener's emotional journey and key tension points in one line. Example:
Arc: Curiosity → Tension → Anti-Hook Twist → Micro-Loop Teaser → Revelation → Resolve
State this briefly to the user.

**Step 2 — Write:**
Read `references/hindi-voice-guide.md` and follow all narration rules defined there.

Write the full script to:
`library/<project_name>/script.md`

#### Script Format:
```markdown
# Script: <Approved Title>
Description: <Approved Description>

---

[Full narration script in flowing Hindi paragraphs, with quotes in > blockquotes]
```

- Write as a continuous, flowing narrative in pure prose with natural punctuation (`...`, `—`).
- Use subtle, low-intensity prosody nudges (`[Subtle warmth]`, `[Conversational tone]`, `[Brief pause]`, `[Slightly slower]`). NEVER use extreme vocal verbs like `[Whisper]`, `[Shout]`, or `[Crying]` as they distort TTS synthesis.
- Structure with paragraph breaks, inserting a micro open-loop teaser every ~100–120 words (~45–60 seconds of audio).

---

### Revision Mode

If the user provides feedback on a completed script:
- **Structural feedback** (wrong arc, bad pacing, missing point): Re-present a revised template, then rewrite.
- **Tonal feedback** (too formal, too preachy, too flat): Rewrite directly, adjusting register and voice.
- Always state what changed before overwriting `script.md`.

---

## Hard Rules

- **Wait for Blueprint Approval:** Never write the full script before the user picks a title and blueprint.
- **Keep the separator:** Always include the `---` line before the narration body. Production treats everything after the first `---` as the narration zone.
- **Blockquotes are visual-only:** Lines in `>` are NOT spoken. They are rendered on screen as styled text.
- **Pure Prose:** No scene splits, image prompts, or metadata brackets in `script.md`.
- **Update status:** Once the script is written, update `session.json` status to `"compose_complete"`.