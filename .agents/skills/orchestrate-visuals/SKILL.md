---
name: orchestrate-visuals
description: Visual concept design & prompt orchestration skill. Reads scenes.json skeleton from split-script, discovers/registers character visual identities, and writes context-rich image prompts and img2img references for every scene. Runs after split-script, before voice.
---

# Orchestrate-Visuals Skill

This skill is the **cinematographer and visual director**. It takes the lean skeleton produced by `split-script` and focuses 100% of its attention on visual storytelling: *what visual composition best holds the emotional truth of each scene, how do we maintain character visual identity across the story, and how do we chain images for smooth visual continuity?*

It does not split text. It does not calculate word counts. It thinks purely in visual narrative rhythm, camera framing, lighting registers, and character identity.

---

## When to Activate

Activate this skill when:
- `session.json` exists with `status: "split_complete"`
- `scenes.json` exists with all `image_prompt` fields set to `null`

---

## Step 1 — Read Inputs & Identify Characters

Read the following files before doing anything:
1. `library/<project_name>/session.json` → extract `visual.style`, `visual.aspect_ratio`, and `voice.language`
2. `library/<project_name>/scenes.json` → read all scenes (`id`, `text`)
3. `library/<project_name>/script.md` → read the **full script** to understand the story arc, setting, recurring characters, and key props

### Character Identification

Scan `script.md` for all **recurring main characters** — those requiring consistent visual identity across multiple scenes.

**Character Key Naming Rule:** `snake_case`, lowercase. Omit honorifics unless part of the character's common name (e.g. `osho`, `lord_krishna`, `the_seed`, `young_monk`).

For each recurring character, write a 30–50 word visual description for their `prompt` field. Write only what the camera sees — no abstract qualities like "wise" or "brave":

- **Real historical or spiritual figure**: Anchor strictly to documented visual record (age, clothing, headwear, posture, defining facial features). Do not invent traits.
- **Fictional human character**: Derive from the story's own descriptions. For any unspecified detail, make one consistent choice and hold it across all scenes.
- **Non-human protagonist** (seed, river, tree, animal, object): Always write as an **anthropomorphized character** — give it expressive eyes, a readable face, and an emotional range across the story arc (e.g. fearful and trembling early on, determined and straining mid-story, triumphant and wide-eyed at resolution). Describe body shape, surface texture, and limbs if physically plausible. The render quality is governed by `visual.style`; the character description governs who this character *is* and how its face carries emotion.

The pipeline appends `characters[key].prompt` to every prompt at generation time — **do not copy this description into `image_prompt`**.

---

## Step 2 — Define `characters` Dictionary

Write the top-level `"characters"` object in `scenes.json`. Use the character's common display name for `canonical_name` — no parenthetical variants:

**Example — real figure:**
```json
"characters": {
  "osho": {
    "canonical_name": "Osho",
    "prompt": "a serene Indian mystic in his 50s–60s, long silver-white beard, bald head, wearing a flowing white robe and a large ornate white cap, deep-set calm eyes, unhurried composed posture"
  }
}
```

**Example — non-human protagonist:**
```json
"characters": {
  "the_seed": {
    "canonical_name": "The Seed",
    "prompt": "a small round seed character with large expressive eyes, tiny stubby arms, smooth warm-brown shell — fearful and trembling in dark underground scenes, determined and straining when pushing upward through soil, wide-eyed with joy and relief at emergence into light"
  }
}
```

---

## Step 3 — Cinematographic Craft Rules

Apply these rules when writing every scene's prompt.

### A. Camera Framing Cadence

**Hard Rule:** Never use the same camera framing for two consecutive scenes. Rotate across:
- `Intimate Close-up` — facial emotion, eyes, subtle expressions
- `Medium Shot` — gestures, upper body, interaction with immediate environment
- `Wide Environmental Shot` — establishing location, atmosphere, scale
- `Low-Angle Shot` — authority, triumph, quiet heroism
- `Over-the-Shoulder` — observer perspective

### B. Lighting Register Language

Map the story's emotional arc to explicit lighting descriptors in `image_prompt`:

| Emotion Register | Lighting Language to Embed |
|---|---|
| Wisdom / Peace / Reflection | `warm golden hour light, soft amber candlelight, gentle rim lighting` |
| Fear / Doubt / Conflict | `moody deep blues, heavy chiaroscuro shadows, cold atmospheric contrast` |
| Effort / Struggle | `warm amber glow cutting through darkness, low dramatic side lighting` |
| Triumph / Epiphany / Breakthrough | `high-contrast golden light breaking through, radiant backlighting, glowing warmth` |

### C. Pattern Interrupt Cadence

Every 3–4 scenes, introduce a deliberate visual shift to hold audience attention. Use one of:
- **Scale shift**: Cut from intimate or medium framing to a wide or aerial shot, resetting visual scale
- **Symbolic metaphor frame**: Replace the literal scene with a pure visual metaphor — no character in frame (e.g. roots spreading like rivers of gold, a flame holding steady against wind, a single crack of light breaking through stone)

---

## Step 4 — Prompt Assembly & Scene Chaining

### A. Prompt Formula

`visual.style` from `session.json` is the **global style prefix** — it defines the render quality and visual register for every image. Embed it literally at the start of every `image_prompt`. Do not rely on the pipeline to add it.

**Scenes with a referenced character** (`"referenced_characters"` non-empty):
```
[visual.style], [Character Canonical Name] — [Emotion & Posture] — [Environment & Lighting] — [Camera Framing]
```

**Example:**
`"premium cinematic digital painting, vivid colors, dramatic lighting, Osho — hands open, palms upward in quiet offering, a faint knowing smile — warmly lit meditation hall, soft amber candlelight — medium shot"`

**Scenes without a referenced character** (`"referenced_characters"` empty):
```
[visual.style], [Visual Subject] — [Action or Symbolic Meaning] — [Environment & Lighting] — [Camera Framing]
```

**Example:**
`"premium cinematic digital painting, vivid colors, dramatic lighting, A solitary oil lamp — flame holding steady against a rising wind, casting long shadows — dim stone temple interior, cool blue-grey ambient light — intimate close-up"`

> [!IMPORTANT]
> Use only the character's `canonical_name` as the subject anchor in `image_prompt`. Never copy or paraphrase the character's `prompt` description string into `image_prompt` — the rendering pipeline prepends it automatically at generation time.

### B. In-Image Text Language

Any text rendered visibly inside the generated image must be written in the script of `voice.language` from `session.json` — not English.

### C. Scene Chaining (`reference_scene_id`)

| Situation | `reference_scene_id` | `reference_weight` |
|---|---|---|
| Same character, same environment | prior scene id | `0.65` |
| Same character, new environment | prior scene id | `0.40` |
| New independent scene | `null` | `null` |

`reference_scene_id` must always point **backward** — never to a scene with a higher index than the current scene.

---

## Step 5 — Write `scenes.json`

Full overwrite of `library/<project_name>/scenes.json`:

```json
{
  "project_name": "osho-pyaas-ki-keemat",
  "visual_style": "premium cinematic digital painting, vivid colors, mystical lighting",
  "total_words": 180,
  "scene_count": 9,
  "characters": {
    "osho": {
      "canonical_name": "Osho",
      "prompt": "a serene Indian mystic in his 50s–60s, long silver-white beard, bald head, wearing a flowing white robe and a large ornate white cap, deep-set calm eyes, unhurried composed posture"
    }
  },
  "scenes": [
    {
      "id": "scene-006",
      "text": "> प्रेम स्वतंत्रता है।",
      "referenced_characters": ["osho"],
      "image_prompt": "premium cinematic digital painting, vivid colors, mystical lighting, Osho — eyes half-closed in deep stillness, a faint knowing smile — seated in a warmly lit meditation hall — soft golden hour light — intimate close-up",
      "reference_scene_id": null,
      "reference_weight": null,
      "image_path": null
    },
    {
      "id": "scene-007",
      "text": "> जब तुम किसी को प्रेम करते हो, तो तुम उसे मुक्त करते हो।",
      "referenced_characters": ["osho"],
      "image_prompt": "premium cinematic digital painting, vivid colors, mystical lighting, Osho — hands open and raised slightly, palms facing upward in a gesture of release — warmly lit meditation hall — warm amber candlelight — medium shot",
      "reference_scene_id": "scene-006",
      "reference_weight": 0.65,
      "image_path": null
    }
  ]
}
```

Then update `session.json` → set `session.status` to `"storyboard_complete"`.

---

## Hard Rules

1. **No character prompt duplication.** Use the character's `canonical_name` as the subject in `image_prompt`. The pipeline prepends `characters[key].prompt` automatically at generation time.
2. **No consecutive camera framing.** Adjacent scenes must never share the same framing. Check the prior scene before assigning the current one.
3. **Backward-only scene chaining.** `reference_scene_id` must always point to a prior scene — never forward-reference.
4. **Character keys are `snake_case`.** Use the same key consistently in `characters{}` and every `referenced_characters` array.
5. **Non-human protagonists are always anthropomorphized in their character description.** If the story's protagonist is a seed, animal, river, or object, its `characters[key].prompt` must give it expressive eyes and a readable emotional range. The render style is `visual.style`'s concern — the emotional face is this skill's concern.
6. **Safety filter compliance.** Avoid `"piercing gaze"`, explicit body descriptors. Use `"calm gaze"`, `"serene posture"`, `"resolute expression"`.
7. **Vertical composition for 9:16.** When `visual.aspect_ratio` is `9:16`, keep primary subjects centered horizontally in frame.
