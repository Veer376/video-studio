# Scene production

Use this reference only after the relevant clip briefs are approved.

## Prepare the scene

1. Read the approved clip brief, adjacent clips, creative contract, character map, and existing scene records.
2. Identify the recurring consistency-critical characters required by the selected clip and make each one ready by following [character-readiness.md](character-readiness.md).
3. Use `reference_scene_id` only when the predecessor's final composition should become the literal opening frame.
4. If continuity is requested, inspect the predecessor's exact final frame before prompt creation.
5. Invoke the project-local `direct-video-scene` skill with the approved clip brief, creative contract, adjacent scene states, ready characters, and inspected continuity evidence. Use its directed-scene contract as the creative input to prompt production.

## Create and persist the prompt

1. Before invoking `compile-omni-scene`, identify which of the following risks apply to the current clip: multiple recurring characters in frame, spatial geometry that must be stable (facing direction, position), complex motion or contact, Hindi dialogue, or deliberate cuts with character continuity. Record the applicable risks and the mitigation you will use (e.g., exact character count, `No scene cuts`, first-frame lock). Pass these risks and mitigations explicitly in the invocation brief.
2. Proceed prompt creation independently with the directed-scene contract, approved clip brief, verified reference inputs, exact dialogue and audio requirements, continuity evidence, and the recorded risk mitigations.
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
