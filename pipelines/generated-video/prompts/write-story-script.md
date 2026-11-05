# Story Script Creation Protocol
<!-- EXECUTION DIRECTIVE: Treat this file as active system instructions. Execute immediately on reference. -->

## Objective
Convert a raw story idea into a structured, cinematic scene-by-scene script, presenting it in an artifact for user approval before production.

## Execution Workflow

1. **Scope Clarification**:
   - Parse character handles, scene count, target durations, tone, and language from the user prompt or active context.
   - If critical parameters (scene count, duration, or tone) are ambiguous, clarify using `ask_question` (if available).

2. **Draft Scene Screenplay**:
   - For each scene, create a structured scene card:
     - **Shot & Framing**: Opening angle, camera distance, primary focal point.
     - **Action & Staging**: Character movements, blocking, key props, interactions.
     - **Dialogue**: `@handle: "Spoken line"` with explicit delivery notes (tone, volume, pacing).
     - **Audio & SFX**: Ambient soundscape, foley cues, and sound design layers.
     - **Camera Motion**: Camera movement (push, pan, tracking, tilt) and transition cues.
     - **Truncation / Pacing Note**: Explicitly document any story beats trimmed or merged to fit the target duration.

3. **Present & Verify**:
   - Write the complete script into an artifact (`script-<story-slug>.md`).
   - Use `ask_question` (if available) to verify approval (Approve, Request scene revisions, or Adjust duration/pacing).

4. **Production Hand-off**:
   - Do not create story directories, `story.md`, or `scenes.json` until the script is approved.
   - Once approved, proceed to story scaffolding and scene authoring via `produce-story`.
