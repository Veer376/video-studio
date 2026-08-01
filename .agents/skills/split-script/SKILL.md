---
name: split-script
description: Script-splitting skill. Reads script.md and divides the narration prose into scenes at natural sentence boundaries. Writes a lean scenes.json skeleton (no image prompts yet). Runs after compose, before design-visuals.
---

# Split-Script Skill

This skill is the **film editor**. Its only job is precision: it reads the narration prose and makes one decision for every scene — *exactly where does this scene begin and end?* It does not design images. It does not think about visuals. It thinks only about text rhythm, pacing, and word counts.

---

## When to Activate

Activate this skill when:
- `session.json` exists with `status: "compose_complete"`
- `script.md` is written and contains the approved narration
- `scenes.json` does not yet exist (or you are re-splitting)

---

## Step 1 — Read All Inputs

Read the following files before doing anything:
1. `library/<project_slug>/session.json` → extract `project_slug`, `visual.style`
2. `library/<project_slug>/script.md` → extract the full narration body

**Extracting the narration body from `script.md`:**
Strip everything that is not the spoken prose itself:
- Strip any markdown frontmatter (title, date, description, template name)
- Strip any section headers (`##`, `---`)
- Strip stage directions (lines beginning with `[`, e.g. `[medium pause]`, `[excitedly]`)
- Take only the flowing spoken text

Count the total words in the cleaned narration body. This is `total_words`.

---

## Step 2 — Split the Script Intelligently

**Goal:** Divide the narration into chunks at semantically meaningful boundaries, aiming for 1 image (scene) every 8–10 seconds of spoken narration.

> In spoken Hindi, 8–10 seconds corresponds to roughly **18–22 words**. Standardize on a target of **20 words per scene**.

**Algorithm:**

1. Calculate the dynamic scene count:
   ```
   target_scene_count = max(2, round(total_words / 20))
   ```

2. Compute the target words per scene:
   ```
   target_words_per_scene = total_words / target_scene_count
   ```

3. Walk the text word by word, tracking a running word count:
   - When the running count reaches `target_words_per_scene`, look ahead to find the **nearest sentence-ending boundary** (`।`, `.`, `!`, `?`, or `...`) within a 15-word lookahead window.
   - Cut there. **Never cut mid-sentence.**
   - If no sentence boundary is found within the lookahead, cut at the closest natural pause (`,`).

4. Assign sequential IDs to the resulting chunks: `scene-001`, `scene-002`, etc.

> [!IMPORTANT]
> Scene splits must always fall at natural language breaks. Never cut mid-sentence. Never cut mid-thought. A listener should never notice where one scene ends and the next begins.

---

## Step 3 — Assign Word Ranges

For every scene chunk, calculate the inclusive zero-indexed word range:
- `word_range[0]` = index of the **first** word in this chunk
- `word_range[1]` = index of the **last** word in this chunk

> [!IMPORTANT]
> Word ranges must be **contiguous with no gaps and no overlaps**. The last word index of scene N must be exactly one less than the first word index of scene N+1. The final scene's last word index must equal `total_words - 1`.

---

## Step 4 — Write `scenes.json`

Write the skeleton manifest to `library/<project_slug>/scenes.json`.

**Schema — exactly this, nothing more, nothing less:**
```json
{
  "project_slug": "<from session.json>",
  "visual_style": "<session.json visual.style string>",
  "total_words": 847,
  "scene_count": 20,
  "scenes": [
    {
      "id": "scene-001",
      "text": "<full narration text for this scene>",
      "word_range": [0, 42],
      "image_prompt": null,
      "image_path": null,
      "start_time": null,
      "end_time": null
    }
  ]
}
```

**Field rules:**
- `text`: The exact narration prose for this scene. No modifications.
- `word_range`: `[start_index, end_index]` — zero-indexed, inclusive.
- `image_prompt`: `null` — will be filled by the `design-visuals` skill.
- `image_path`: `null` — will be filled by the `illustrate` skill.
- `start_time` / `end_time`: `null` — will be filled after the `voice` skill generates audio.
- `visual_style`: Store the raw string from `session.json visual.style`. If it is a nested object, extract only the string value.

> [!CAUTION]
> Do **not** add any other fields. Do not add `narration`, `subtitle`, `audio_path`, `duration_seconds`, `motion`, `transition`, or `voice_direction`. These fields are either redundant with `text` or belong to the render pipeline — not this manifest.

---

## Step 5 — Update Status

Update `session.json`:
- Set `session.status` to `"split_complete"`

---

## Hard Rules

- **Do not split mid-sentence.** Ever.
- **Do not write image prompts.** That is the `design-visuals` skill's job.
- **`word_range` must be contiguous and cover the entire script** with no gaps or overlaps.
- **Scene count is dynamically determined** based on script length (~20 words per scene), with a minimum of 2 scenes.
- **`visual_style` must be a plain string**, not a nested JSON object.
