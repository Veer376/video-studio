---
name: compose
description: Generate or revise narration scripts from completed story research through blueprint approval and script writing. Use when session.json has research_complete, research.md exists, and script.md is missing or the user requests a rewrite. Routes vertical Shorts, standard scripts, and >=480-second long-form scripts to distinct duration rules.
---

# Compose Skill

This skill is a **screenwriter and storyteller**. Its job is to translate raw research findings into an emotionally resonant narration script through a structured two-round process.

---

## Inputs

Read these files before presenting blueprints:

- `library/<project_name>/session.json`
- `library/<project_name>/research.md`

Read `brief.target_duration_seconds` and `visual.aspect_ratio`, then select exactly one mode:

- **Short:** `visual.aspect_ratio` is `9:16` and `target_duration_seconds <= 180`. Read `references/duration_rules/short.md`. Its drafting gate is mandatory.
- **Standard:** `< 480` seconds and not Short mode. Preserve natural pacing; treat the target as approximate.
- **Long:** `>= 480` seconds. Read `references/duration_rules/long.md`; treat the target as approximate.

Do not infer mode from filename or a platform label alone. A contemporary YouTube Short must be square or vertical and no longer than three minutes; this pipeline's Short format is `9:16`.

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

- **Short mode:** Use the Short blueprint contract in `references/duration_rules/short.md`.
- **Standard or Long mode:** Generate 3 distinct templates using:

`TEMPLATE — Macro Loop (0:00-0:15): <Hook + Anti-hook pair> Micro Loops: <Tension teasers at ~60s intervals> Middle arc: <How the story builds and connects to modern life — two sentences> Turn: <The emotional pivot or revelation — one sentence> Closing: <The final call to action or resolution — one sentence> Tone signature: <e.g., Rising inspiration, quiet contemplation, dramatic epic>`

**Wait for the user's explicit selection before proceeding to Round 2.**

---

### Round 2: Script Writing

Once the user approves a title and template:

**Step 1 — Emotional Arc & Retention Anchors:**
Before writing, state the listener's emotional journey in one line. Follow the selected duration-mode structure. Example for Standard or Long mode:

`Arc: Curiosity → Tension → Anti-Hook Twist → Micro-Loop Teaser → Revelation → Resolve`

**Step 2 — Write:**
Read `references/hindi-voice-guide.md` and follow all narration rules defined there.
If a duration-mode reference conflicts with an optional narration device, the duration-mode reference wins.

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
- In Standard or Long mode, use paragraph breaks and insert a micro open-loop teaser every ~100–120 words (~45–60 seconds of audio).
- In Short mode, do not use periodic micro-loops. Follow the single-loop structure and completion gate in `references/duration_rules/short.md`.

---

### Revision Mode

If the user provides feedback on a completed script:
- **Structural feedback** (wrong arc, bad pacing, missing point): Re-present a revised template, then rewrite.
- **Tonal feedback** (too formal, too preachy, too flat): Rewrite directly, adjusting register and voice.
- **Short duration failure:** Compress directly while preserving the approved hook and payoff. Re-present a blueprint only if either must change.
- Always state what changed before overwriting `script.md`.

---

## Hard Rules

- **Wait for Blueprint Approval:** Never write the full script before the user picks a title and blueprint.
- **Keep the separator:** Always include the `---` line before the narration body. Production treats everything after the first `---` as the narration zone.
- **Blockquotes are visual-only:** Lines in `>` are NOT spoken. They are rendered on screen as styled text.
- **Pure Prose:** No scene splits, image prompts, or metadata brackets in `script.md`.
- **Short gate:** Do not write or approve a Short that fails `references/duration_rules/short.md`.
- **Update status:** Update `session.json` to `"compose_complete"` only after the applicable duration-mode rules pass.
