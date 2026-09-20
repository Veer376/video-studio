# Scene production

Use this reference only after the relevant clip briefs are approved.

## Prepare the scene

1. Read the approved clip brief, adjacent clips, creative contract, character map, location map, narration requirements, and existing scene records. If the selected production root contains `production-playbook.md`, read it completely before directing the scene and treat its production-specific camera, blocking, geography, retention, motif, and sound grammar as authoritative unless it conflicts with locked story facts.
2. Identify the recurring consistency-critical characters and locations required by the selected clip. Make every character ready by following [character-readiness.md](character-readiness.md), and verify every recurring location has an existing registered reference image and concise stable profile before prompt creation.
3. When the selected clip continues the same physical moment as its predecessor, inspect the predecessor's exact final frame before prompt creation.
4. Use `reference_scene_id` when that inspected frame should become the literal opening anchor. Do not use it for an intentional discontinuity such as a change of time, place, perspective, or composition.
5. Invoke the project-local `direct-video-scene` skill with the approved clip brief, creative contract, adjacent scene states, ready characters, and inspected continuity evidence. Use its directed-scene contract as the creative input to prompt production.

## Create and persist the prompt

1. Before invoking `compile-omni-scene`, identify which of the following risks apply to the current clip: multiple recurring characters in frame, recurring-location continuity, spatial geometry that must be stable (facing direction, position, entrances/exits), complex motion or contact, Hindi dialogue, or deliberate cuts with character continuity. Record the applicable risks and the mitigation you will use (e.g., exact character count, registered `@location-*` reference, `No scene cuts`, first-frame lock). Pass these risks and mitigations explicitly in the invocation brief.
2. Proceed prompt creation independently with the directed-scene contract, approved clip brief, verified reference inputs, exact dialogue and audio requirements, continuity evidence, and the recorded risk mitigations.
3. Keep recurring identities explicit in the authoring prompt: character `@handles`, registered `@location-*` handles, and any `@narration-*` voice handle. The runner resolves characters and locations to ordered visual references and narration handles to audio-only profiles.
4. Every recurring character handle in the prompt must be listed in the scene's `subjects`. Every recurring `@location-*` handle in the prompt must be listed in the scene's `locations`. Narration handles belong in the prompt only, not in either declaration array.
5. Do not describe a registered recurring place only in free text. Use its `@location-*` handle whenever that exact place is visually present, including alternate camera angles, interiors/exteriors that are covered by the same canonical location identity, and return shots used for payoff continuity.
6. Use `reference_images` only for scene-specific supplemental material (evidence objects, temporary diagrams, special composition references). Do not use it as a substitute for a registered character or location.
7. Author and persist prompts strictly one scene at a time. Never draft or persist multiple scene prompts in a single pass.
8. Store the final prompt and scene references in `scenes.json`; do not create an extended prompt.

## Project craft layer

When a production root contains `production-playbook.md`, scene production must not reduce the task to merely making the plot beat visible. Before prompt creation, verify that the proposed clip has an intentional first-read focal point, a visible state change or attention handoff, motivated camera behavior, and a useful ending image. Do not fall back to generic cinematic defaults when the playbook defines a stronger production-specific visual grammar.

## Continuity policy

- A wrong identity or object in a literal first frame can persist despite a clean loose reference.
- A wrong location reference can distort geography across later clips. Prefer the registered location image plus the predecessor's inspected final frame when both identity and exact moment continuity matter.
- Do not add more references merely to make an instruction stronger. Use only references with a distinct required role.
- If an inspected first frame contains a local defect, either describe its correction at the start of the next clip or create one surgically corrected continuity frame that preserves all correct composition.
- When a curated composite already contains the required cast correctly, treat it as the authoritative first frame and avoid redundant character references that introduce duplication.
- Reduce simultaneous recurring characters and isolate cast by shot when identity or count begins to drift.

These are recovery policies, not guarantees of model consistency.

## Generate

1. Generate the current scene with `--scene <scene-id>`. The runner writes directly to the scene's `output_path`.
2. Review the active video and persist the evidence and decision in `reviews/<scene-id>.json`.
3. If accepted, continue to the next scene; the active video already has its final name.
4. If it needs fixing, revise the scene or prompt and run the normal generation command once more. The runner archives the rejected video and its contact sheet before creating the replacement. If the replacement also fails, it archives that video and stops for user direction.
