# Production stage

The primary production contract is documented in the pipeline `README.md` and `scripts/production/README.md`. Read those before running or resuming production. Commands run from the image-story pipeline directory.

1. Generate/reuse narration units with `story-video voice-step narrate`, transcribe with `voice-step transcribe`, and align with `voice-step align`. Inspect the spoken audio and scene/word timings.
2. Plan and inspect the visual dependency graph with `produce-visuals plan`; use `run --images-only --dry-run` before generation. The approved `session.json` visual lock, scene prompts, and continuity file are authored inputs.
3. Generate selected assets with `produce-visuals run`, inspect them, and record any required continuity anchor approval. Respect durable job/idempotency state and explicit retry rules.
4. Validate and assemble using `render-story --project-dir <project> --dry-run`, then render. Verify video/audio playback, captions, duration, and the requested aspect ratio before reporting completion.

The runtime owns fingerprints, manifests, references, writer locks, retries, and validation. Do not reconstruct or erase its state to bypass a gate. Existing generated video supersedes stills only when the producer marks it complete. Voice, picture, and caption inputs must agree before rendering.

For imported productions already using the older `story-video run/stage` contract, follow that CLI's compatible state and repository `config.json`; its illustration/render state is distinct. Do not silently switch an existing production between contracts. Normal new production uses the primary path above.

Use regeneration/force only within the user's authorized scope. Generation and transcription are billable; alignment and rendering are local. For a requested Short, probe the actual final duration and resolve an overlong result through script/scene revision rather than silently speeding or truncating narration.
