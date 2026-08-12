# Scene Direction

## Build a Continuity Ledger

Derive a compact internal ledger from the script and existing scenes. Do not add it to `scenes.json`.

Track only facts that must persist:

- recurring appearance and clothing
- location, architecture, era, season, weather, and time of day
- key props, ownership, count, and state
- spatial relationships and action progression
- transformations, injuries, or damage

Resolve uncertainty in this order: scene text, full script, sourced research, compatible established scene, then the least-specific non-claiming visual choice. Omit unnecessary unknowns.

## Choose the Still

For each scene identify the exact primary beat, required visible subjects and props, forbidden contradictions or premature outcomes, and inherited continuity.

- Depict the dominant visible action; do not replace it with mood, symbolism, or a nearby event.
- Include every action-critical participant, recipient, pursuer, object, and interaction.
- Do not reveal an outcome early or carry a completed action into a later beat.
- For abstract narration without literal action, prefer a truthful reaction, consequence, or established motif. Use pure metaphor only when it clarifies rather than interrupts the sequence.
- Let camera, lighting, and variation serve the beat. Repeating the clearest framing is valid.
- Motivate lighting from place, time, and visible sources. Avoid automatic golden revelation or blue conflict lighting.
- Replace aura, energy, wisdom, courage, and divinity with visible posture, gesture, expression, light, or environment unless the narration explicitly requires a supernatural effect.

## Write the Prompt

Production prepends `visual_style` and appends non-null character prompts. Do not duplicate either.

```text
[Canonical subject(s)] — [exact visible action and interaction] — [continuity-critical environment, era, props, and state] — [motivated lighting] — [camera framing and composition]
```

Use registered `canonical_name` values and list their keys in `referenced_characters`. Describe one-scene characters inline rather than registering background extras.

For period scenes, exclude plausible modern defaults when their appearance would be false. Keep 9:16 action and principal subjects readable inside the central safe region.

Avoid visible text unless narration requires a specific inscription, document, or sign. When required, reproduce only the exact source text appropriate to `voice.language`.

## Chain Scenes Carefully

Set `reference_scene_id` to a backward compatible scene only when its visible composition, subject state, props, and environment form a valid continuity base. Otherwise use null.

Production owns provider-specific reference mapping. Do not write reference-strength controls.
