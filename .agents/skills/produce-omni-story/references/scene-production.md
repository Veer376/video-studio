# Scene production

Use this reference only after the relevant clip briefs are approved.

## Prepare the scene

1. Read the approved clip brief, adjacent clips, creative contract, character map, and existing scene records.
2. Register only recurring consistency-critical characters. Describe one-off figures directly in the prompt.
3. Use `reference_scene_id` only when the predecessor's final composition should become the literal opening frame.
4. If continuity is requested, inspect the predecessor's exact final frame before prompt creation.

## Create and persist the prompt

1. Invoke `omni-flash-prompt-writer` independently with the approved clip brief, verified reference inputs, exact dialogue and audio requirements, and continuity evidence.
2. Keep project `@handles` in the authoring prompt. The runner resolves them to ordered `<IMAGE_REF_N>` inputs.
3. Present the prompt before or alongside persistence. In an authorized batch, persist prompts in scene order and report the completed range.
4. Store the final prompt and scene references in `scenes.json`; do not create an extended prompt.

## Continuity policy

- A wrong identity or object in a literal first frame can persist despite a clean loose reference.
- Do not add more references merely to make an instruction stronger. Use only references with a distinct required role.
- If an inspected first frame contains a local defect, either describe its correction at the start of the next clip or create one surgically corrected continuity frame that preserves all correct composition.
- When a curated composite already contains the required cast correctly, treat it as the authoritative first frame and avoid redundant character references that introduce duplication.
- Reduce simultaneous recurring characters and isolate cast by shot when identity or count begins to drift.

These are recovery policies, not guarantees of model consistency.

## Generate

1. Run the generator in dry-run mode first.
2. Generate the user-selected scene, part, or missing range. Existing valid canonical videos are skipped by default.
3. A scene with a missing `reference_scene_id` output remains blocked until its predecessor exists.
4. After generation, hand every new clip to the review phase before generating a dependent clip.
