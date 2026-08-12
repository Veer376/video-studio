# Manifest Contract and Fidelity Gate

Preserve top-level fields and every scene's `id` and `text`. Add or update only:

- top-level `characters`
- scene `referenced_characters`
- scene `image_prompt`
- scene `reference_scene_id`
- scene `image_path`

Remove legacy `reference_weight`. Do not erase valid timing, image paths, or unrelated production fields during a revision.

## Scene Shape

```json
{
  "id": "scene-004",
  "text": "नरेंद्र भागने लगे, तो बंदर और भी तेज़ पीछे दौड़े!",
  "referenced_characters": ["swami_vivekananda"],
  "image_prompt": "Swami Vivekananda — running down a narrow stone lane while rhesus macaques chase within a few steps behind him — late-19th-century temple passage, wet flagstones, one wooden staff, no modern signs — overcast morning light — vertical wide tracking shot",
  "reference_scene_id": "scene-003",
  "image_path": null
}
```

## Fidelity Gate

Reject and correct a scene if any answer is no:

- Does it depict the same narration beat and chronology?
- Are all action-critical subjects and props present and acting correctly?
- Is every registered key defined and every canonical name used consistently?
- Is anything unsupported, duplicated, anachronistic, contradictory, or premature?
- Does it preserve established identity, environment, prop, and time continuity?
- Are historical or devotional specifics supported rather than inferred?
- Do camera and lighting serve the beat rather than replace it?
- Is the prompt concrete and renderable without abstract labels?
- Is any shared asset choice visually inspected and mapped with correct reuse/adaptation semantics?

## Final Rules

- Narration fidelity outranks beauty, symbolism, and shot variety.
- Character keys are lowercase `snake_case`.
- Never duplicate `visual_style` or stable character descriptions in `image_prompt`.
- Never add unsupported decorative writing.
- Preserve later session status during corrections.
- State which existing scene images require forced regeneration.
