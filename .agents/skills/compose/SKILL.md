---
name: compose
description: Script-generation skill. Orchestrates the two-round process of blueprint presentation and script writing. Delegates narration craft to reference files.
---

# Compose Skill

This skill is a **screenwriter and storyteller**. It translates raw research into an emotionally resonant narration script through a structured two-round process.

---

## When to Activate

- `session.json` exists with `status: "research_complete"`
- `research.md` is written and available
- `script.md` does not yet exist, or the user wants to rewrite/regenerate

---

## Inputs

Read `library/<project_slug>/session.json` before writing.
Treat `target_duration_seconds` as a rough script-length target, not a strict constraint.

---

## Research Selection

Not all research belongs in the script. Select from `research.md` using:
1. Does it serve the emotional arc?
2. Does it surprise the listener?
3. Does it deepen the core conflict?

If a fact doesn't serve the story, cut it.

---

## Round 1: Blueprint Presentation

Present **3 Titles, 1 Description, and 3 Template Blueprints**.

**Titles** — one of each:
1. **Curiosity Gap:** Hidden knowledge hook.
2. **Emotional Conflict:** Core human struggle.
3. **Direct Challenge:** Speaks to the viewer's situation.

**Description** — 2–3 sentences summarizing the video's promise without spoiling the turn. One emotional keyword, one curiosity trigger.

**Templates:**
TEMPLATE — Opening hook: <First 8 seconds — one sentence> Middle arc: <Story build + modern connection — two sentences> Turn: <Emotional pivot — one sentence> Closing: <Resolution or call to action — one sentence> Tone signature: <e.g., Rising inspiration, quiet contemplation>

**Wait for explicit user selection before Round 2.**

---

## Round 2: Script Writing

**Step 1 — Emotional Arc:**
Define the listener's journey in one line. State it to the user.
Arc: Curiosity → Tension → Doubt → Revelation → Resolve

**Step 2 — Write:**
Follow `references/hindi-voice-guide.md` for all narration rules.
If the script includes shlokas or quotes, also follow `references/quote-rendering-rules.md`.

Write to: `library/<project_slug>/script.md`

**Format:**
```markdown
# Script: <Approved Title>
Description: <Approved Description>

---

[Narration in flowing Hindi prose, quotes in > blockquotes]
```

- Write as one continuous, flowing narrative in pure prose.
- No scene numbers, image prompts, or voice directions.
- The ONLY non-prose element allowed is `>` blockquotes for shlokas/quotes.
- Structure with paragraph breaks only.

---

## Revision Mode

- Structural feedback (arc, pacing, missing point): Re-present revised template, then rewrite.
- Tonal feedback (too formal, flat, preachy): Rewrite directly with adjusted register.
- State what changed before overwriting `script.md`.

---

## Hard Rules

- Never write the full script before user picks a title and blueprint.
- Always include `---` before narration body. Production treats everything after it as the narration zone.
- `>` blockquote lines are visual-only — not spoken, rendered on screen as styled text.
- No scene splits, image prompts, or metadata in `script.md`. Pure prose only.
- Update `session.json` status to `"compose_complete"` when done.