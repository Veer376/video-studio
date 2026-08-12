# Character Identity and Shared Assets

Register only recurring main characters or subjects that need stable identity across scenes. A character may be human, animal, plant, object, landscape feature, or mythological figure.

## Identify and Describe

Use lowercase `snake_case` keys. Use the common display name as `canonical_name`.

Write `prompt` as a concise stable visual identity description only. Exclude scene-dependent action, emotion, lighting, camera language, and `visual.style`.

- Historical or spiritual figures: use only details supported by project evidence or a stable documented visual record appropriate to the depicted period. Do not infer exact age, clothing, headwear, location, or date from identity alone.
- Fictional humans: use story details; make one restrained consistent choice where a visible trait is necessary but unspecified.
- Non-human subjects: preserve the story's treatment. Never add faces, limbs, or expressions to a naturalistic subject.

## Search the Shared Catalog

Before proposing a new asset, search repository-root `assets/characters/`. Inspect plausible files visually; filenames alone are insufficient.

Judge each candidate against:

- correct subject identity and stable traits
- compatibility with `visual.style`
- suitability for the target aspect ratio and readable subject framing
- sufficient quality, clean visibility, and no unwanted text or extra subjects
- truthful treatment: illustration versus photograph, naturalistic versus anthropomorphic, and correct period/state

Do not search arbitrary project folders as a shared catalog. Shared assets live only under repository-root `assets/characters/`.

## Choose One Mapping

### Reuse a suitable shared asset unchanged

Use the portable `root:` locator and set `prompt` to null:

```json
"osho": {
  "canonical_name": "Osho",
  "prompt": null,
  "image_path": "root:assets/characters/osho-painted.png"
}
```

Production validates and references the shared image directly. It never copies or overwrites it.

### Adapt a useful but unsuitable shared asset

Keep the shared image as the source and provide a stable identity prompt:

```json
"osho": {
  "canonical_name": "Osho",
  "prompt": "an Indian mystic with a long silver-white beard, bald head, and deep-set dark eyes",
  "image_path": "root:assets/characters/osho-photo.png"
}
```

Use this when identity is useful but style, orientation, framing, background, or medium conflicts with the project. Production uses the root image as an identity reference, creates `assets/characters/osho.png`, and changes `image_path` to that local path only after success.

Do not put adaptation commands in `prompt`; production supplies the neutral identity-sheet composition and project style.

### Generate a new project-local asset

When no suitable shared source exists:

```json
"the_seed": {
  "canonical_name": "The Seed",
  "prompt": "a small round warm-brown seed character with a smooth shell and two tiny physically plausible arms",
  "image_path": null
}
```

Production assigns `assets/characters/the_seed.png`, persists that path, and generates the missing local asset. Existing valid local assets resume without regeneration.

## Null-Prompt Safety

`prompt: null` means the shared image is the entire identity specification. Use it only when that character's image can fit into every scene's reference budget. A prior scene consumes one of four reference slots.

If a crowded scene can omit the character image, provide a stable textual prompt instead. Production fails before spending credits when an omitted character has no prompt fallback.

## Invariants

- `root:` locators must remain under repository-root `assets/`.
- Use `image_path: null` for a new asset. Production owns assignment of its project-local locator.
- Existing project-local locators must remain under the current project's `assets/characters/`.
- Never point a canonical character at a scene image.
- Never overwrite, move, or silently restyle a shared root asset.
- Do not generate assets from this skill.
