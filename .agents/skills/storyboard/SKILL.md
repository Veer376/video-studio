---
name: storyboard
description: Scene-creation skill. Reads the approved script.md and intelligently splits it into scenes with rich, cinematically-aware image prompts. Writes the initial scenes.json manifest. Runs after compose.
---

# Storyboard Skill

This skill is a **film director and visual designer**. It reads the final narration prose and makes two decisions for every scene: *where does this scene begin and end?* and *what single image best holds the emotional meaning of this full scene?*

---

## When to Activate

Activate this skill when:
- `session.json` exists with `status: "compose_complete"`
- `script.md` is written and contains the approved narration
- `scenes.json` does not yet exist

---

## Step 1 — Read All Inputs

Read the following files before doing anything:
1. `library/<project_slug>/session.json` → extract `visual.style`
2. `library/<project_slug>/script.md` → extract the full narration text (strip the title, template name, date, description header — take only the flowing prose body)

Count the total words in the narration body. This is `total_words`.

---

## Step 2 — Split the Script Intelligently

**Goal:** Divide the narration into chunks at semantically meaningful boundaries, aiming for 1 image (scene) every 8–10 seconds of spoken narration. (In spoken Hindi, this corresponds to roughly 1 scene per 18–22 words, standardizing on a target of 20 words per scene).

**Algorithm:**
1. Calculate the dynamic scene count:
   ```
   target_scene_count = max(2, round(total_words / 20))
   ```
2. Compute the target words per scene:
   ```
   target_words_per_scene = total_words / target_scene_count
   ```

Walk the text word by word, tracking a running word count:
1. When the running count reaches `target_words_per_scene`, look ahead to find the **nearest sentence-ending boundary** (full stop `।`, `.`, `!`, `?`, or an ellipsis `...`) within a 15-word lookahead window.
2. Cut there. Do not cut in the middle of a sentence.
3. If no sentence boundary is found within the lookahead, cut at the closest natural pause (comma).

> [!IMPORTANT]
> Scene splits must always fall at natural language breaks. Never cut mid-sentence. Never cut mid-thought. A listener should never notice where one scene ends and the next begins.

The result is a list of `N` text chunks. Assign sequential IDs: `scene-001`, `scene-002`, etc.

---

## Step 3 — Design Each Image Prompt

This is the most important step. For each scene chunk, you are writing a description for an image that will be **displayed for the full duration of that scene** (approximately `seconds_per_scene` seconds). The image must hold its meaning for the entire duration — not just represent the first or last action in the narration.

### The "Hold the Meaning" Principle
Read the full text of the scene chunk and ask: **What is the single dominant emotional state or visual reality of this scene?** That is your image subject.

- **Wrong approach:** Illustrate the first or last action ("Arjuna's bow falling")
- **Right approach:** Illustrate the sustained emotional truth ("A great warrior's inner collapse — outwardly still, inwardly shattered")

The image must be something a viewer can look at for 10–12 seconds and continue feeling the narration's emotion.

---

### The Image Prompt Formula

Structure every prompt using these five elements:

```
[Subject] — [Emotional State] — [Environment] — [Lighting & Atmosphere] — [Composition]
```

**Subject:** Who or what is the visual anchor of this scene.
**Emotional State:** The sustained feeling this image must convey (not an action — a state).
**Environment:** The physical setting grounding the scene.
**Lighting & Atmosphere:** Match the emotional register of the narration (dark/cool for conflict, golden/warm for revelation, soft/misty for contemplation).
**Composition:** The camera framing (wide epic establishing shot / intimate close-up / over-the-shoulder / top-down / silhouette).

**Example — Scene narrating Arjuna's deep doubt:**
> `Arjuna — overwhelmed with grief and doubt, shoulders slumped, eyes downcast — seated in a grand war chariot surrounded by two massive opposing armies — dramatic overcast light, dust-filled air, deep shadows — mid-shot intimate framing, armies softly out of focus in the background`

**Example — Scene narrating Krishna's calm revelation:**
> `Lord Krishna — radiating unshakeable serenity and divine wisdom — standing on the chariot reins holding loosely in his hands — warm golden-hour light, soft halo of luminous amber, battlefield fading into soft mist — three-quarter portrait shot, tight on face, eyes full of deep knowing compassion`

---

### Visual Continuity Rules

Design the full sequence of images as a directed film — not a collection of independent illustrations. Follow these rules:

1. **Alternate compositions:** Never place the same framing in two consecutive scenes. If scene 3 is a wide epic shot, scene 4 should be close or mid-shot.
2. **Evolve the palette with the arc:**
   - *Conflict/Doubt scenes:* Cooler tones, heavy shadows, overcast light.
   - *Revelation scenes:* Warmer golden hour, subtle ambient glow.
   - *Final/Resolution scenes:* Bright, expansive, wide compositions.
3. **Maintain spatial logic:** If a scene is on the battlefield, the next should still feel grounded in that world unless the narration explicitly moves elsewhere.
4. **Vary subject scale:** Alternate between individual characters in close focus and wide scenes showing the larger context.
5. **Flow test:** After writing all prompts, read them in sequence. Does the visual journey feel like a film? Does each image logically follow from the previous?
6. **Character & Prop Consistency (Visual Sheets):** For any project, establish a strict visual identity sheet for all key recurring characters, weapons, and vehicles. Inject these exact descriptions into every scene prompt where they appear to ensure character continuity:
   - *Exampl :*
     - **Arjuna:** `Arjuna (a handsome young Indian warrior prince, curly black hair tied in a bun, wearing traditional bronze armor and a red sash)`
     - **Lord Krishna:** `Lord Krishna (a serene divine young man with dark blue skin, a peacock feather in his golden crown, wearing a brilliant yellow silk dhoti and a gentle smile)`
     - **Bow Gandiva:** `the ancient golden bow Gandiva, decorated with glowing Sanskrit engravings`
   - *Example (Modern corporate theme):*
     - **Protagonist:** `Rohan (a young Indian businessman, wearing a sharp dark gray suit, glasses, and a silver wristwatch, neat short hair)`
7. **Visual Context Anchoring (No Isolated Objects):** Never prompt for a floating object or hand in a void. Always anchor it to the character's clothing, weapons, or the environment (e.g. show the bow on Arjuna's shoulder, or show hands wearing a silver wristwatch holding a pen at a wooden office desk).

---

### The Global Visual Style Prefix

Every prompt is prepended with the `visual.style` value from `session.json` when the image generator runs. You do not need to repeat the style in each prompt. Write only the subject-specific part.

*Example:*
`session.json` has `visual.style: "premium cinematic digital painting, vivid colors, mystical lighting, ancient India"`
Your prompt: `"Arjuna seated in chariot, face buried in hands..."`
What Flux receives: `"premium cinematic digital painting, vivid colors, mystical lighting, ancient India — Arjuna seated in chariot, face buried in hands..."`

---

## Step 4 — Write `scenes.json`

Write the complete manifest to `library/<project_slug>/scenes.json`.

**Schema:**
```json
{
  "project_slug": "<from session.json>",
  "visual_style": "<session.json visual.style>",
  "total_words": 847,
  "scene_count": 20,
  "scenes": [
    {
      "id": "scene-001",
      "text": "<full narration text for this scene>",
      "word_range": [0, 42],
      "image_prompt": "<scene-specific image prompt — without the style prefix>",
      "image_path": null,
      "start_time": null,
      "end_time": null
    }
  ]
}
```

**Field notes:**
- `word_range`: `[start_word_index, end_word_index]` (zero-indexed, inclusive). Used later for Groq timestamp alignment.
- `image_path`: `null` until the `illustrate` skill runs.
- `start_time` / `end_time`: `null` until the `voice` skill generates audio and Groq timestamps are extracted.
- `visual_style`: Stored here so the `illustrate` skill does not need to re-read `session.json`.

---

## Step 5 — Update Status

Update `session.json`:
- Set `session.status` to `"storyboard_complete"`

---

## Hard Rules

- **Do not split mid-sentence.** Ever.
- **Each image prompt must represent the sustained emotional state**, not a momentary action.
- **Think like a director:** every prompt decision should consider what precedes and follows it.
- **Do not generate images.** This skill only writes `scenes.json`. The `illustrate` skill handles image generation.
- **`word_range` must be contiguous and cover the entire script** with no gaps or overlaps.
- **Scene count is dynamically determined based on script length** (aiming for 1 scene per 8–10 seconds, or ~20 words per scene), with a minimum of 2 scenes.
