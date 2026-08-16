# Scene production

Use this reference only after the relevant clip briefs are approved.

## Prepare the scene

1. Read the approved clip brief, adjacent clips, creative contract, character map, and existing scene records.
2. Identify the recurring consistency-critical characters required by the selected clips. For each one, verify that `characters.json` contains a valid reference path and that the image exists.
3. If a required recurring reference is missing, create the character image from the approved story description, inspect it for the intended identity and design, save it under project `assets/characters/` when reusable across stories or under the selected story's `assets/` when story-specific, and register it in `characters.json`. Ask the user only when a missing design choice would materially change the character. Do not begin prompt creation until every required recurring reference is ready.
4. Use `reference_scene_id` only when the predecessor's final composition should become the literal opening frame.
5. If continuity is requested, inspect the predecessor's exact final frame before prompt creation.

## Create and persist the prompt

1. Before invoking `omni-flash-prompt-writer`, identify which of the following risks apply to the current clip: multiple recurring characters in frame, spatial geometry that must be stable (facing direction, position), complex motion or contact, Hindi dialogue, or deliberate cuts with character continuity. Record the applicable risks and the mitigation you will use (e.g., exact character count, `No scene cuts`, first-frame lock). Pass these risks and mitigations explicitly in the invocation brief.
2. Proceed prompt creation independently with the approved clip brief, verified reference inputs, exact dialogue and audio requirements, continuity evidence, and the recorded risk mitigations.
3. Keep project `@handles` in the authoring prompt. The runner resolves them to ordered `<IMAGE_REF_N>` inputs.
4. Author and persist prompts strictly one scene at a time. Never draft or persist multiple scene prompts in a single pass.
5. Store the final prompt and scene references in `scenes.json`; do not create an extended prompt.

## Continuity policy

- A wrong identity or object in a literal first frame can persist despite a clean loose reference.
- Do not add more references merely to make an instruction stronger. Use only references with a distinct required role.
- If an inspected first frame contains a local defect, either describe its correction at the start of the next clip or create one surgically corrected continuity frame that preserves all correct composition.
- When a curated composite already contains the required cast correctly, treat it as the authoritative first frame and avoid redundant character references that introduce duplication.
- Reduce simultaneous recurring characters and isolate cast by shot when identity or count begins to drift.

These are recovery policies, not guarantees of model consistency.

## Generate

1. Run the generator in dry-run mode first.
2. Generate the current scene with `--scene <scene-id> --attempt <number>`. The runner writes `temp/partial/<scene-id>-attempt-<number>.mp4`; it does not change the canonical video.
3. Review the candidate and persist its attempt entry before deciding whether to retry or promote it.
4. Set `selected_attempt` in the review, then use `--promote-attempt <number>` to copy only that reviewed candidate to the scene's canonical `output_path`.
5. Existing valid canonical videos are skipped unless regeneration is explicitly authorized. Regeneration still creates a candidate and leaves the current canonical file untouched until promotion.