# Split-Script Stage

This stage is the **film editor**. Its only job is precision: read the narration prose and decide exactly where each scene begins and ends. Do not design images; consider only text rhythm, pacing, and word counts.

---

## When to Run

Run this stage when:
- `session.json` exists with `status: "compose_complete"`
- `script.md` is written and contains the approved narration
- `scenes.json` does not yet exist (or you are re-splitting)

---

## Step 1 — Read All Inputs

Read the following files before doing anything:
1. `library/<project_name>/session.json` → extract `project_name`, `visual.style`
2. `library/<project_name>/script.md` → extract the full narration body

**Extracting the narration body from `script.md`:**
Strip everything that is not the spoken prose itself:
- Strip any markdown frontmatter (title, date, description, template name)
- Strip any section headers (`##`, `---`)
- Strip stage directions (lines beginning with `[`, e.g. `[medium pause]`, `[excitedly]`)
- Take only the flowing spoken text
- Lines in `script.md` beginning with `>` are quotes, maxims, or sacred shlokas. **DO NOT STRIP THE `>` MARKER.**

**Tokenizer Definition:**
A word is any non-whitespace token after removing non-spoken Markdown lines. Punctuation remains attached to its neighbouring token (e.g. `गया।`). All downstream skills must use this same definition.

Count the total words in the cleaned narration body. This is `total_words`.

---

## Step 2 — Split the Script Intelligently

**Goal:** Divide the narration into chunks at semantically meaningful boundaries, aiming for 1 image (scene) every **7–9 seconds** of spoken narration for high visual retention.

> In spoken Hindi, 7–9 seconds corresponds to roughly **16–20 words**. Standardize on a target of **18 words per scene**.

**Algorithm & Semantic Boundary Scoring:**

1. Calculate target scene count:
   ```
   target_scene_count = max(2, round(total_words / 18))
   ```

2. Compute target words per scene:
   ```
   target_words_per_scene = total_words / target_scene_count
   ```

3. Walk the text word by word, tracking running word count:
   - Near `target_words_per_scene`, search **both backward (-8 words) and forward (+10 words)** for candidate sentence boundaries (`।`, `.`, `!`, `?`, or `...`).
   - If multiple candidate boundaries exist, score candidates using semantic hierarchy:
     - **Paragraph Break / Subject Change:** Highest priority split point (+8)
     - **Full Sentence Ending:** High priority (+6)
     - **Question / Exclamation Ending:** High priority (+5)
     - **Q&A Cohesion:** Keep question and answer together in the same scene if under 30 words.
     - **Dangling Connectors:** Avoid splitting immediately before connector words (`लेकिन`, `क्योंकि`, `और तभी`, `इसलिए`, `मगर`) if the preceding thought is needed for context.
   - Cut at the highest scoring boundary.
   - **Hard Rule:** Never cut mid-sentence. Never cut at commas (`,`). If no sentence boundary exists in the search window, allow the scene to extend up to 30 words to reach the next full sentence end.
   - **Quote Continuity Rule:** If a quote block (lines marked by `>`) is split across multiple scenes, **EVERY continuation scene** of that quote MUST also begin with the `> ` prefix so downstream renderers activate quote vignette styling continuously.

4. Assign sequential IDs to the resulting chunks: `scene-001`, `scene-002`, etc.

> [!IMPORTANT]
> Scene splits must always fall at natural language breaks. Never cut mid-sentence. Never cut mid-thought. A listener should never notice where one scene ends and the next begins. If a quote spans multiple scenes, every continuation scene MUST retain the `> ` prefix.

---

## Step 3 — Write `scenes.json`

Write the skeleton manifest to `library/<project_name>/scenes.json`.

**Schema — exactly this, nothing more, nothing less:**
```json
{
  "project_name": "<from session.json>",
  "visual_style": "<session.json visual.style string>",
  "total_words": 400,
  "scene_count": 20,
  "scenes": [
    {
      "id": "scene-001",
      "text": "<full narration text for this scene>",
    }
  ]
}
```

**Field rules:**
- `text`: The exact narration prose for this scene. No modifications, except ensuring that all quote and quote-continuation scenes MUST begin with the `> ` prefix.
- `visual_style`: Store the raw string from `session.json visual.style`. If it is a nested object, extract only the string value.

> [!CAUTION]
> Do **not** add any other fields. Do not add `narration`, `subtitle`, `audio_path`, `duration_seconds`, `motion`, `transition`, or `voice_direction`. These fields are either redundant with `text` or belong to the render pipeline — not this manifest.

---

## Step 4 — Update Status

Update `session.json`:
- Set `session.status` to `"split_complete"`

---

## Hard Rules

- **Do not split mid-sentence or at commas.** Ever.
- **Do not write image prompts.** That belongs to the standalone `orchestrate-visuals` skill.
- **Scene count is dynamically determined** based on script length (~18 words per scene), with a minimum of 2 scenes.
- **`visual_style` must be a plain string**, not a nested JSON object.
- **Multi-scene quotes MUST preserve `> ` on all continuation scenes.** Never drop `> ` from subsequent quote scenes.
