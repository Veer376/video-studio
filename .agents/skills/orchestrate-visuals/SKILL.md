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

## Step 1 — Read Inputs & Search Existing Character Assets

Read the following files before doing anything:
1. `library/<project_name>/session.json` → extract `visual.style` and `brief.language`
2. `library/<project_name>/scenes.json` → read all scenes (`id`, `text`)
3. `library/<project_name>/script.md` → read the **full script** to understand the story arc, setting, recurring characters, and key props

### Character Asset Discovery Protocol:
Before writing prompts, scan `script.md` for all **recurring main characters** — those requiring consistent visual identity across multiple scenes — including historical and spiritual figures (e.g. Osho, Swami Vivekananda, Lord Krishna, Buddha, Gandhi).

**Character Key Naming Rule:** Derive each character's key in `snake_case`, lowercase. Omit honorifics unless they are part of the character's common name (e.g. `osho`, `lord_krishna`, `older_monk`, `swami_vivekananda`). The character's image asset is saved using this same key (e.g. `assets/characters/older_monk.png`).

For each identified character:

1. Check if an existing master character image exists in global assets. Extension lookup precedence: `png > jpg > jpeg > webp`:
   - Check `assets/characters/<character_key>.png` (or `.jpg`, `.jpeg`, `.webp`)
2. If an existing image path is found:
   - Assign `"image_path": "assets/characters/<character_key>.png"` in `scenes.json` under `"characters"`.
3. If **no** existing image is found in `assets/characters/`:
   - Set `"image_path": null`.
   - Write a character model turnaround reference sheet prompt in `characters[key]["prompt"]` formatted as: `"Character concept model sheet turnaround showing full front view, side profile view, back view, and facial close-up detail — <40–50 word description of age, beard/hair, face, attire, headwear> — solid plain grey studio background"`.

---

## Step 2 — Define Top-Level `characters` Dictionary

In `scenes.json`, write a top-level `"characters"` object. Use the common name only for `canonical_name` — no parenthetical variants:

```json
"characters": {
  "osho": {
    "canonical_name": "Osho",
    "prompt": "Character concept model sheet turnaround showing full front view, side profile view, back view, and facial close-up detail — Osho (a serene Indian mystic in his 50s–60s, long silver-white beard, bald head, wearing a flowing white robe and a large ornate white cap, deep-set expressive eyes with a calm knowing gaze) — solid plain grey studio background",
    "image_path": null
  }
}
```

---

## Step 3 — Cinematographic Framing & Lighting Craft Rules

Apply these internal craft rules when planning scene prompts:

### A. Camera Framing Cadence (No Consecutive Framing Rule)
**Hard Rule:** Never use the same camera framing for two consecutive scenes. Rotate across:
- `Intimate Close-up` (facial emotion, eyes, subtle expressions)
- `Medium Waist-up Shot` (gestures, upper body posture, interaction with immediate environment)
- `Wide Environmental Shot` (establishing location, atmosphere, crowd dynamics)
- `Low-Angle Hero Shot` (quiet authority, majestic posture)
- `Over-the-Shoulder / Third Person` (observer perspective)

### B. Emotional Color & Lighting Registers
Map the story's emotional progression to explicit lighting descriptors in `image_prompt`:
- **Wisdom / Reflection / Peace**: `Warm golden hour light, soft amber candlelight, gentle rim lighting, soft sunbeams`
- **Conflict / Doubt / Fear**: `Moody deep blues, heavy chiaroscuro shadows, rain-streaked reflections, dark atmospheric contrast`
- **Triumph / Epiphany**: `High-contrast golden light breaking through storm clouds, radiant backlighting, glowing ambient warmth`

### C. Pattern Interrupt Cadence
Every 3–4 scenes, introduce a dramatic perspective shift or dynamic visual contrast. Use one of:
- **(a) Scale shift** — switch from an intimate framing (close-up, medium) to a wide or aerial shot to reset the visual scale
- **(c) Surreal / symbolic metaphor frame** — replace literal scene depiction with an abstract visual metaphor (e.g. a river of fire, a figure dissolving into light, a crumbling clock face)

---

## Step 4 — Concise Prompt Assembly & Scene Chaining

For each scene, assemble `image_prompt` and determine img2img reference chaining.

### A. Concise Prompt Assembly Rule

**Scenes with named characters** (`"characters": ["osho"]`, etc.):
If a character key is listed in scene `"characters"`, **do NOT duplicate the 50-word baseline character description in `image_prompt`**.

Construct `image_prompt` using this 4-part formula:
$$\text{Prompt} = [\text{Character Key}] + \text{" — "} + [\text{Posture \& Expression}] + \text{" — "} + [\text{Environment \& Lighting}] + \text{" — "} + [\text{Camera Framing}]$$

**Example**:
`"Osho — hands open and raised slightly, palms facing upward in a gesture of release — warmly lit meditation hall, soft amber candlelight — medium shot from waist up"`

**Scenes without named characters** (`"characters": []`):
Use the fallback formula for abstract, symbolic, or establishing shots:
$$\text{Prompt} = [\text{Visual Subject}] + \text{" — "} + [\text{Symbolic or Physical Action}] + \text{" — "} + [\text{Environment \& Lighting}] + \text{" — "} + [\text{Camera Framing}]$$

**Example**:
`"A solitary oil lamp — flame flickering against a rising wind, casting long shadows across stone floor — dim stone temple interior, cool blue-grey ambient light — intimate close-up"`

### B. In-Image Text Language Rule
Read `session.json["brief"]["language"]`. Any text to be rendered **visibly inside the generated image** (e.g. calligraphic quote overlays, signs, manuscript writing, inscriptions) must be written in that language, not English.

### C. Scene Chaining & Reference Rules (`reference_scene_ids`)

**Single-character scene:**
- **Scene Continuation / Extension**: If Scene N+1 continues Scene N's physical setup (e.g. subject shifts posture from listening to speaking, or a thought bubble appears), set:
  - `"reference_scene_ids": ["scene-N"]`
  - `"reference_weight": 0.65` (same environment) or `0.40` (new environment, same character)
- **Character Seeding**: If Scene N introduces a character without prior scene continuation, set:
  - `"reference_scene_ids": ["characters/osho.png"]` (if character image exists or is pre-generated) or `[]` if generating fresh from prompt.
- **New Independent Scene**: Set `"reference_scene_ids": []` and `"reference_weight": null`.

**Multi-character scene** (when `"characters"` lists two or more keys):
- If continuing a prior scene: include the prior scene ID **and** asset paths for any newly introduced characters in `reference_scene_ids`.
- If it is the first appearance of a character combination: list each character's asset path (if available). If no assets exist yet, set `"reference_scene_ids": []` and generate fresh.
- Example: `"reference_scene_ids": ["scene-003", "characters/disciple.png"]` with `"reference_weight": 0.50`.

**Reference Weight Guide:**

| Situation | Weight |
|---|---|
| Same character, same environment (scene continuation) | 0.65 |
| Same character, new environment | 0.40 |
| Multi-character, mixed references | 0.50 |
| New independent scene | null |

---

## Step 5 — Write `scenes.json`

Update `library/<project_name>/scenes.json` with the complete updated manifest (full overwrite, not a patch):

```json
{
  "project_name": "osho-pyaas-ki-keemat",
  "visual_style": "premium cinematic digital painting, vivid colors, mystical lighting",
  "total_words": 180,
  "scene_count": 9,
  "characters": {
    "osho": {
      "canonical_name": "Osho",
      "prompt": "Character concept model sheet turnaround showing full front view, side profile view, back view, and facial close-up detail — Osho (a serene Indian mystic in his 50s–60s, long silver-white beard, bald head, wearing a flowing white robe and a large ornate white cap, deep-set expressive eyes with a calm knowing gaze) — solid plain grey studio background",
      "image_path": null
    }
  },
  "scenes": [
    {
      "id": "scene-006",
      "text": "> प्रेम स्वतंत्रता है।",
      "characters": ["osho"],
      "image_prompt": "Osho — radiating quiet inner certainty, eyes half-closed in deep stillness, a faint knowing smile — seated in a warmly lit meditation hall — soft golden hour light — intimate close-up",
      "reference_scene_ids": [],
      "reference_weight": null,
      "image_path": null
    },
    {
      "id": "scene-007",
      "text": "> जब तुम किसी को प्रेम करते हो, तो तुम उसे मुक्त करते हो।",
      "characters": ["osho"],
      "image_prompt": "Osho — hands open and raised slightly, palms facing upward in a gesture of release and offering — warmly lit meditation hall — warm amber candlelight — medium shot from waist up",
      "reference_scene_ids": ["scene-006"],
      "reference_weight": 0.65,
      "image_path": null
    }
  ]
}
```

Update `session.json` status to `"storyboard_complete"`.

---

## Hard Rules

1. **Check existing global character assets first.** Always inspect `assets/characters/` before setting `"image_path": null`. Extension precedence: `png > jpg > jpeg > webp`.
2. **Never duplicate character baseline descriptions** inside `image_prompt` when the character key is listed in `"characters": [...]`.
3. **No consecutive camera framing.** Rotate composition across adjacent scenes.
4. **Reference scene IDs must point to prior scenes or character asset paths** — never forward-reference a scene that has not yet been written.
5. **Character keys are `snake_case`.** Image assets are saved and looked up using the same key name.
6. **In-image text must match `brief.language`** from `session.json` — not English, unless English is the brief language.
