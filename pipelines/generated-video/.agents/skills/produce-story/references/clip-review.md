# Clip review

Use this reference after every generated, edited, or regenerated clip.

If the selected production root contains `production-playbook.md`, read its production-specific review gate before deciding whether the active clip is acceptable. Technical validity, correct identity, and correct dialogue are necessary but are not sufficient when the playbook requires a first-read focal point, visible state change, retention function, motivated camera, location geography, or motif continuity.

## Evidence gate

1. Use `ffprobe` to verify duration, dimensions, frame rate, codecs, and both video and audio streams.
2. Extract the exact first frame, exact final frame, and a one-frame-per-second contact sheet for a 10-second clip.
3. Inspect the contact sheet for temporal coverage and the full-resolution frames for faces, hands, props, text, blocking, and continuity.
4. If a possible defect occurs between baseline samples, extract denser full-resolution frames around that timestamp.
5. If dialogue or voiceover is specified in the clip contract, transcribe or directly verify the audio track. A clip with unverified dialogue cannot be marked `accepted` or `accepted_with_note`; mark it `needs_fix` with reason `audio_unverified` if no audio evidence is available.

Store the active video's contact sheet at `temp/contact_sheets/<scene-id>.png` and record its path in the review.

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

Persist the decision and active-video evidence at `reviews/<scene-id>.json` using the artifact contract.

## Repair

For `needs_fix`, diagnose before spending another generation:

1. accept harmless variation;
2. correct a local ending defect in the next scene or with one curated continuity frame;
3. use one surgical video edit for one isolated defect;
4. regenerate with a targeted prompt change;
5. simplify the shot or visible cast when the failure is caused by complexity or conflicting references.

Make one diagnosed replacement at most. It must address the recorded failure with a concrete change; never repeat an unchanged generation request. Review the replacement from fresh evidence.

Stop when the decision becomes `accepted`, `accepted_with_note`, or `fix_next_scene`. If the replacement still returns `needs_fix`, stop and ask the user whether to restore an archived video or revise the scene manually.
