---
name: design-visuals
description: Visual concept design skill. Reads the scenes.json skeleton from split-script and writes a rich, cinematically-consistent image_prompt for every scene. Builds character/prop visual sheets from the story context and injects them into every relevant prompt. Runs after split-script, before voice.
---

# Design-Visuals Skill

This skill is the **concept artist and cinematographer**. It picks up the lean skeleton that `split-script` produced and focuses 100% of its attention on one task: *what single image best holds the emotional truth of each scene, and how do we ensure the characters look identical across all images?*

It does not split text. It does not calculate word counts. It only thinks visually.

---

## When to Activate

Activate this skill when:
- `session.json` exists with `status: "split_complete"`
- `scenes.json` exists with all `image_prompt` fields set to `null`

---

## Step 1 — Read All Inputs

Read the following files before doing anything:
1. `library/<project_name>/session.json` → extract `visual.style`
2. `library/<project_name>/scenes.json` → read all scenes (id, text, word_range)
3. `library/<project_name>/script.md` → read the **full script** to understand the story arc, setting, and recurring characters/props

Do not modify any existing field. You will only fill in `image_prompt` for each scene.

---

## Step 2 — Build the Visual Identity Sheets

Before writing a single prompt, identify all **recurring characters, props, and vehicles** in the story. For each one, write a precise visual sheet — a compact description that fixes their appearance in stone.

**How to build a sheet:**
- Extract from the story: who are the main characters? What are they wearing? What props do they carry?
- Write a **parenthetical identity clause** for each character: `Name (specific physical description, clothing, key distinctive features)`.
- Write a **prop description** for each key object.

**Examples of good visual sheets:**

| Story Type | Sheet Example |
|---|---|
| Ancient epic | `Arjuna (a handsome young Indian warrior prince, curly black hair tied in a bun, wearing traditional bronze armor and a red sash)` |
| Ancient epic | `Lord Krishna (a serene divine young man with dark blue skin, a peacock feather in his golden crown, wearing a brilliant yellow silk dhoti and a gentle smile)` |
| Motivational / boy | `Raju (a thin 10-year-old Indian boy, short messy black hair, wearing a torn white kurta and bare feet)` |
| Modern corporate | `Rahul (a young Indian entrepreneur, short neat hair, wearing a dark gray suit jacket and white shirt, no tie)` |
| Historical | `Swami Vivekananda (a young Bengali monk, shaved head, wearing a simple saffron robe, piercing determined eyes)` |

> [!IMPORTANT]
> Once you define a sheet for a character, you **must copy-paste the exact parenthetical clause verbatim** into every prompt where that character appears. Do not paraphrase. Do not write "the same boy". The image model has no memory — every prompt is independent.

---

## Step 3 — Design Each Image Prompt

For every scene in `scenes.json`, read the scene's `text` and design one image prompt.

### The "Hold the Meaning" Principle

Read the full scene text and ask: **What is the single dominant emotional state or visual reality of this entire scene?** That is your image subject.

- ❌ **Wrong:** Illustrate a momentary action (`"Arjuna dropping his bow"`)
- ✅ **Right:** Illustrate the sustained emotional truth (`"A great warrior's inner collapse — still on the outside, shattered on the inside"`)

The image must be something a viewer can look at for 10–12 seconds and continue feeling the narration's emotion.

---

### The Image Prompt Formula

Structure every prompt using these five elements:

```
[Subject] — [Emotional State] — [Environment] — [Lighting & Atmosphere] — [Composition]
```

- **Subject:** The visual anchor of this scene. **Always include the full character sheet if a character appears.**
- **Emotional State:** The sustained feeling this image must convey (not an action — a state).
- **Environment:** The physical setting grounding the scene.
- **Lighting & Atmosphere:** Match the emotional register (dark/cool for conflict and doubt, golden/warm for revelation, bright/expansive for resolution).
- **Composition:** The camera framing (wide epic establishing shot / intimate close-up / over-the-shoulder / top-down / silhouette).

**Example — scene about a boy's perseverance:**
> `Raju (a thin 10-year-old Indian boy, short messy black hair, wearing a torn white kurta and bare feet) — exhausted but unbroken, face streaked with dust and sweat, small hands gripping a heavy stone chisel — dry cracked earth under a blazing noon sun, ancient Indian village in the far background — harsh direct sunlight, haze shimmering from the ground, deep warm amber shadows — low angle shot looking up at the boy, shallow depth of field`

**Example — scene about the same boy's triumph:**
> `Raju (a thin 10-year-old Indian boy, short messy black hair, wearing a torn white kurta and bare feet) — overcome with pure joy and wonder, arms raised, face tilted to the sky — standing next to a cracked rock from which a clear sparkling spring of water gushes — lush green sprouts emerging from wet soil around his feet — soft golden hour light, shimmering water droplets catching the light — wide establishing shot, boy small against a dramatic sky`

---

### Visual Continuity & Retention Rules

Design the full sequence as a **directed film** — not a collection of independent illustrations.

1. **Alternate compositions:** Never place the same framing in two consecutive scenes. Wide shot → close-up → mid-shot, etc.
2. **3-Scene Cadence Gate (Visual Pattern Interrupts):** Never allow 3 consecutive scenes to share the same framing scale or color tone. Every 3rd scene (~20–25 seconds) MUST introduce a stark Visual Pattern Interrupt (e.g. switching from an environmental wide shot to an extreme emotional close-up or high-contrast lighting shift) to reset viewer visual fatigue.
3. **Evolve the color palette with the story arc:**
   - *Conflict/Doubt scenes:* Cool tones, heavy shadows, overcast light.
   - *Rising action scenes:* Warmer amber tones, growing light.
   - *Revelation/Resolution scenes:* Bright, expansive, golden warm light, wide frames.
4. **Maintain spatial logic:** If the story is set on a battlefield, every scene should still feel grounded in that world unless the narration explicitly moves elsewhere.
5. **Vary subject scale:** Alternate between individual characters in close focus and wide scenes showing the larger context.
6. **Visual Context Anchoring:** Never prompt for a floating object or hand in a void. Always anchor props to the character's body or the environment:
   - ❌ `"a bow floating in air"`
   - ✅ `"the golden bow Gandiva resting across Arjuna's bronze-armored shoulder"`
7. **Flow test:** After writing all prompts, read them in sequence. Does the visual journey feel like a film? Does each image logically follow from the previous?

---

### The Global Visual Style Prefix

Every prompt is prepended with the `visual_style` value from `scenes.json` when the image generator runs. **Do not repeat the style in your prompts.** Write only the subject-specific part — the style is added automatically.

*What you write:*
`"Raju (thin 10-year-old Indian boy...) — exhausted but unbroken..."`

*What the image model receives:*
`"premium cinematic digital painting, vivid colors, mystical lighting — Raju (thin 10-year-old Indian boy...) — exhausted but unbroken..."`

---

## Step 4 — Write Image Prompts Back to `scenes.json`

Update `library/<project_name>/scenes.json` — fill in the `image_prompt` field for every scene. Do not modify any other field.

The file after this skill runs should look like:

```json
{
  "project_name": "sample-story",
  "visual_style": "premium cinematic digital painting, vivid colors, mystical lighting, ancient India",
  "total_words": 90,
  "scene_count": 2,
  "scenes": [
    {
      "id": "scene-001",
      "text": "धूल उड़ती रही...",
      "word_range": [0, 47],
      "image_prompt": "Raju (a thin 10-year-old Indian boy, short messy black hair, wearing a torn white kurta and bare feet) — exhausted but unbroken, face streaked with dust and sweat — dry cracked earth under a blazing noon sun — harsh direct sunlight, warm amber shadows — low angle shot looking up at the boy",
      "image_path": null,
      "start_time": null,
      "end_time": null
    }
  ]
}
```

---

## Step 5 — Update Status

Update `session.json`:
- Set `session.status` to `"storyboard_complete"`

---

## Hard Rules

- **Never paraphrase a character sheet.** Copy-paste it verbatim into every prompt where the character appears.
- **Never write "the same character" or "as before."** The image model is stateless — describe them fully every time.
- **Each image prompt must represent the sustained emotional state**, not a momentary action.
- **Never add fields to `scenes.json`.** Only fill in `image_prompt`. Every other field is owned by another skill.
- **Do not split text.** Do not recalculate word counts. That work is already done.
- **Think like a cinematographer:** every composition decision should consider what precedes and follows it.
