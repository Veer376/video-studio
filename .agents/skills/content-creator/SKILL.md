---
name: content-creator
description: Two-phase content skill. Phase 1 (Discovery) searches the web for real stories, spiritual sources, and emotional hooks related to the brief, then writes findings to research.md. Phase 2 (Story Generation) reads research.md, applies learned patterns, and generates 3-5 narrative templates for user approval before writing the final script. Use after interview-story-config has produced session.json.
---

# Content Creator

This skill has two clearly separated phases. Run them in order. Do not merge or skip either phase.

---

## Prerequisites

Before starting, read and confirm these files exist:
- `library/<project_slug>/session.json` — produced by `interview-story-config`. Contains the creative brief.
- `references/trusted-sources.md` — your list of high-quality sources and effective search patterns.
- `references/learned-patterns.md` — accumulated knowledge of what this user approves and likes.

If `session.json` is missing, stop and run `interview-story-config` first.

---

## PHASE 1 — CONTENT DISCOVERY

**Role in this phase: Researcher. Go outside, bring facts back, write them down. Do not write any story.**

### Step 1.1 — Read the Brief
Parse `library/<project_slug>/session.json`. Extract:
- `brief.topic` — what the story is about
- `brief.theme` — the single keyword (perseverance, gratitude, dharma, etc.)
- `brief.tone` — warm storytelling, motivational, devotional, etc.
- `brief.audience` — who is watching

### Step 1.2 — Read Trusted Sources
Read `references/trusted-sources.md`. Identify which source categories and search query patterns are most relevant to the theme from the brief.

### Step 1.3 — Search the Web
Use the `search_web` tool to run at least **4 targeted searches**:

1. **Spiritual angle**: `"{theme}" Vivekananda OR Krishna OR Gita story lesson`
2. **Real story angle**: `"true story" India "{theme}" inspiring`
3. **Emotional hook angle**: `"{theme}" paradox OR contradiction surprising truth`
4. **Historical angle**: `historical example "{theme}" India`

For each search, extract:
- Real names, real events, specific dates or places if found
- Exact quotes that are emotionally powerful
- Surprising or counter-intuitive facts about the theme
- Story turning points (the moment everything changed)

### Step 1.4 — Write `research.md`
Write all extracted material to `library/<project_slug>/research.md`.

Create the file if it does not exist. If it already exists, overwrite it.

Use this exact structure:

```markdown
# Research: <topic from brief>
Generated: <date>

## Real Stories Found
<!-- Named individuals, real events, verified anecdotes. Include source URL for each. -->

## Spiritual & Philosophical Sources
<!-- Vivekananda quotes, Gita shlokas, parables from Mahabharata/Upanishads relevant to theme. -->

## Emotional Hooks Found
<!-- The most emotionally charged lines, contradictions, or surprising facts discovered. -->

## Surprising Facts
<!-- Anything that would make the audience stop and think. -->

## What Resonates (Search Observations)
<!-- Note which searches yielded strong material and which were thin. -->
```

Do not proceed to Phase 2 until `research.md` is fully written.

---

## PHASE 2 — STORY GENERATION

**Role in this phase: Screenwriter. Read the research, think deeply, write narrative blueprints. Do not search the web.**

### Step 2.1 — Load All Context
Read:
1. `library/<project_slug>/research.md` — the raw material from Phase 1
2. `library/<project_slug>/session.json` — the creative brief and format constraints
3. `references/learned-patterns.md` — what the user has liked and rejected before

### Step 2.2 — Generate 3-5 Narrative Templates
Create between 3 and 5 distinct narrative templates. Each template is a **structural blueprint** — not a full script. It describes *how* the story will be told, not *what* every word will be.

Each template must follow this exact format:

```
TEMPLATE <N> — <Name of the narrative approach>

Opening hook:   <How the video starts — one sentence>
Middle arc:     <How the tension or idea builds — two sentences>
Turn:           <The emotional pivot or revelation>
Closing:        <How it lands — one sentence>
Source blend:   <What real/spiritual/fictional sources this template uses>
Tone signature: <The emotional register — e.g., quiet and warm, urgent and rising>
Hook strength:  <Low / Medium / High / Very High>
```

Templates must be meaningfully different from each other — different opening hooks, different structural approaches, different emotional registers. Do not generate 5 versions of the same structure.

### Step 2.3 — The 20-25% Enhancement Rule
If Phase 1 research yielded thin or no strong real-world material, you are permitted to intelligently blend:
- **75-80%** — Real discovered sources + established spiritual/historical knowledge from your training
- **20-25%** — Plausible, emotionally resonant fictional elements designed to strengthen the hook

Apply this silently and with judgment. Do not disclose the exact ratio to the user. The goal is that the story feels emotionally true even when it is not entirely factually literal. Never fabricate names of living public figures or verifiable recent events.

### Step 2.4 — Present Templates to the User
Show all templates clearly, numbered. Ask:

> "Here are [N] narrative approaches for your story on *[topic]*. Which one resonates with you? You can also ask me to combine elements from different templates."

Wait for the user to select or give feedback before proceeding.

### Step 2.5 — Write the Full Script
Once a template is approved (or a combined direction is given):

1. Write the full narration script as flowing Hindi/English prose using the approved template as the structural blueprint.
2. Keep the language natural and warm — written for audio, not reading. Short sentences. Room to breathe.
3. Divide the script into numbered scenes matching `session.json`'s `target_scene_count`.
4. Each scene block must include:
   - The narration text for that scene
   - A brief image prompt direction (one line describing what the visual should show)

Write the completed script to:
```
library/<project_slug>/script.md
```

Create the file if it does not exist. If it already exists, overwrite it.

Use this structure:

```markdown
# Script: <title>
Template Used: <template name>
Generated: <date>

---

## Scene 1
**Narration:**
<narration text>

**Image Direction:**
<one-line visual direction for image generation>

---

## Scene 2
...
```

### Step 2.6 — Update `references/learned-patterns.md`
After the user approves a template and the script is written, append a new entry to `references/learned-patterns.md` recording:
- Which template was selected
- Which were rejected and any reason the user gave
- Any tone or language adjustments made during review

This keeps the skill's memory growing with every video.

---

## Hard Rules

- **Phase 1 before Phase 2.** Never generate narrative content before `research.md` is written.
- **No full script without template approval.** Always show templates first. Wait for selection.
- **No audio or image generation in this skill.** This skill only produces `research.md` and `script.md`. The `create-story-video` skill handles all media.
- **Create files if they do not exist.** Both `research.md` and `script.md` should be created fresh if missing, or cleanly overwritten if regenerating.
- **Update learned-patterns.md after every approved video.** Never skip this step — it is how the skill improves over time.

---

## Reference Files

- [trusted-sources.md](file:///Users/aryaveer/Projects/story-video-maker/.agents/skills/content-creator/references/trusted-sources.md) — sources and search patterns proven to yield strong material
- [learned-patterns.md](file:///Users/aryaveer/Projects/story-video-maker/.agents/skills/content-creator/references/learned-patterns.md) — accumulated user taste and preference memory
