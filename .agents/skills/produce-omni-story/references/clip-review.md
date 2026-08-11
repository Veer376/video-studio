# Clip review

Use this reference after every generated, edited, or regenerated clip.

## Evidence gate

1. Use `ffprobe` to verify duration, dimensions, frame rate, codecs, and both video and audio streams.
2. Extract the exact first frame, exact final frame, and a one-frame-per-second contact sheet for a 10-second clip.
3. Inspect the contact sheet for temporal coverage and the full-resolution frames for faces, hands, props, text, blocking, and continuity.
4. If a possible defect occurs between baseline samples, extract denser full-resolution frames around that timestamp.
5. If dialogue or sound matters, inspect or transcribe the audio separately. Mark it unverified if no audio evidence is available.

Store contact sheets under the selected story's `temp/contact_sheets/` directory.

## Compare with the contract

Review observable evidence against:

- required characters, identity, count, clothing, and position;
- required action, causality, pacing, and ending state;
- speaker and audio requirements when audio evidence exists;
- camera behavior, palette, props, location, and unwanted text;
- predecessor-final and current-first continuity when applicable;
- suitability of the final frame for any dependent scene.

Distinguish harmless creative variation from a story-breaking defect. Report findings with timestamps and observable evidence.

## Decision

Choose the decision by first asking whether the current clip is usable as part of the final story:

- `accepted`: the clip satisfies its required story beat and has no actionable defect.
- `accepted_with_note`: the clip has a harmless visible or creative variation that does not damage the current beat or threaten later continuity.
- `fix_next_scene`: the current clip remains usable, but a late or final-frame inconsistency could propagate through `reference_scene_id`. Use this for correctable identity, clothing, prop, count, or blocking drift that should be restored in a curated first frame or at the start of the next clip.
- `needs_fix`: the current clip itself is unusable or materially misleading. Use this when a character or required object visibly appears, disappears, duplicates, or transforms through an unintended snap; a required subject, action, dialogue, or ending state is missing or wrong; identity drift makes the depicted character ambiguous; or media validation fails.

Never use `fix_next_scene` to excuse a defect that already breaks the current clip. A small inconsistency isolated to the final frame is `fix_next_scene` only when the clip otherwise remains usable and that frame may be used for continuity.

Persist the decision at `reviews/<scene-id>.json` using the artifact contract.

## Bounded repair

For `needs_fix`, diagnose before spending another generation:

1. accept harmless variation;
2. correct a local ending defect in the next scene or with one curated continuity frame;
3. use one surgical video edit for one isolated defect;
4. regenerate with a targeted prompt change;
5. simplify the shot or visible cast when the failure is caused by complexity or conflicting references.

The original generation is attempt 1. The agent may make at most two repair retries, producing attempts 2 through 3. Every retry must address the recorded diagnosis with a concrete change; never repeat an unchanged repair request. After each retry, validate and review the new result and append the attempt to the same review JSON.

Stop retrying immediately when the decision becomes `accepted`, `accepted_with_note`, or `fix_next_scene`. If attempt 3 still returns `needs_fix`, set `next_action` to `await_user` and stop until the user explicitly authorizes further work.
