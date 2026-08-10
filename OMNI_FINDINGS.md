# Omni Flash production findings

Empirical notes from this project. These are workflow observations, not guarantees about the preview model.

## Multi-character continuity

- A literal previous-scene frame can overpower a correct loose character reference. If the previous frame already contains a wrong face, combining both may preserve the wrong figure and add the corrected reference as a duplicate.
- Stacking a composite first frame plus four individual character images caused identity transfer between Gajar and Jadui Bargad. More references did not improve consistency.
- A curated composite first frame removed the input conflict, but the model still duplicated or transformed characters when four named characters, a talking River face and several timed actions shared one clip.
- Changing from multishot to one continuous shot reduced reconstruction but did not eliminate character-count drift. Prompt wording cannot guarantee exact identity or count.

## Working recovery pattern

1. Inspect the predecessor's exact final frame before authoring the next scene.
2. If it has identity drift, create one surgically corrected composite still that preserves its composition.
3. Use that composite as the single authoritative `<FIRST_FRAME>`; avoid stacking every individual character image on top of it.
4. Keep the next clip to the fewest simultaneously visible characters and one dominant cause-action-reaction beat.
5. Generate and visually approve one link in the continuity chain before generating dependent scenes.
6. If one generated clip is otherwise good, prefer one surgical uploaded-video edit over repeated full regenerations.

## API behavior verified here

- Uploaded inline MP4 editing works through the Interactions API with the `edit` task on the configured Enterprise Agent Platform backend.
- `response_format.aspect_ratio` must be omitted for an edit request; the API rejects it with HTTP 400 otherwise.
- The successful `s014` edit removed only the duplicate Gajar and preserved a 10.005-second H.264 video stream and AAC audio stream.

## Current accepted limitation

`s014` now has one correct carrot-headed Gajar after the surgical edit. Chhotu's head still drifts toward a human-haired child later in the clip; this is accepted for this scene and should be corrected at the start of the next scene rather than triggering more paid `s014` retries.

`s015` preserved the corrected vegetable identities initially but copied moving Aloo and Gajar instead of removing their original positions. A surgical uploaded-video edit did not materially change those duplicates, so the canonical clip keeps that accepted inconsistency.

## Pattern validated by later clips

- `s016` used one corrected composite first frame, then isolated coverage: Gajar and Chhotu for setup, Aloo alone for dialogue, Chhotu alone over the water, and Aloo plus Chhotu for the catch. It retained the intended vegetable identities without duplicates.
- `s017` began from the clean Aloo-Chhotu final frame and uploaded only Gajar and Jadui Bargad as loose references. Each later shot showed at most two family members. Gajar stayed carrot-headed and the crossing remained readable.
- The practical rule for this project is therefore shot-level cast isolation, not increasingly forceful identity wording.
- `s026` confirmed the curated-frame recovery pattern for environment geometry as well as faces: replacing an impossible cracked carriage column with one intact steel post in the literal first frame produced a coherent rope anchor while preserving Aloo and Tamatar Guard.
