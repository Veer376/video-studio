---
name: compile-omni-scene
description: "Compile an approved video-scene direction into a Gemini Omni Flash authoring prompt, or revise and diagnose an existing Omni prompt, while respecting Flow and Gemini API capability differences. Use after scene direction is settled or when an Omni result needs prompt-level repair. Do not use to direct the story, serialize provider requests, generate media, or handle unrelated video models."
---

# Compile Omni Scene

Compile one precise Gemini Omni Flash authoring prompt from an approved directed scene. Preserve the direction while applying Omni-specific prompt controls, capability checks, and known-risk mitigations. Repair existing Omni prompts and diagnose failures when requested.

Do not serialize provider requests, call a generation service, render video, edit files, bypass safety controls, or claim that wording guarantees model output.

## Evidence policy

Use this priority when rules conflict:

1. Current dated Google product/API documentation.
2. Current undated Google help and DeepMind prompt guidance.
3. Google-owned GitHub examples.
4. Repeated community evidence.
5. Creative heuristics, clearly treated as best-effort.

Do not carry Veo extension mechanics or Seedance-specific positive-only, FOV, speed, Kelvin, fog-percentage, or fixed-block rules into Omni.

Read [references/surface-capabilities.md](references/surface-capabilities.md) before handling assets, duration, editing, voice/audio references, provider behavior, regional questions, or unsupported capabilities. Read [references/examples.md](references/examples.md) when an example is useful or the correct output shape is uncertain.

Read [references/failure-modes.md](references/failure-modes.md) in two mandatory situations:

1. **Before writing any generation prompt** that involves more than one recurring character, spatial geometry that must remain stable (camera direction, tractor facing, character position), or complex motion. Identify which failure modes apply to the scene and name the mitigation you are applying inside the prompt. This is not optional.
2. **When diagnosing** a failed or poor generation.

## Input authority

When the input includes an approved directed-scene contract or another precise creative plan, treat its dramatic function, beat order, shot architecture, blocking, camera, visual treatment, exact dialogue, sound direction, and continuity as authoritative.

- Translate those decisions into Omni-compatible prompt language without re-directing the scene.
- Apply capability, contradiction, density, asset-role, and known-risk checks.
- Do not replace an intentional choice with a default merely because another choice is easier to prompt.
- If a required decision conflicts with the selected surface or cannot fit the duration, report the smallest necessary adaptation or capability blocker instead of silently changing it.

When the input is only a rough idea, supply the minimum missing direction needed to make it renderable. That fallback does not make this skill the owner of upstream scene direction.

## Output contract

Return exactly one authoring prompt in one fenced `text` block.

For project scenes, preserve registered `@handles`. Do not emit API tags, Flow media IDs, task parameters, aspect-ratio configuration, or other request transport. The runtime provider adapter owns those transformations.

Do not include headings, field labels, a rationale, alternatives, or the internal checklist unless the user asks for them.

Exceptions:

- Ask one short question when a missing choice would materially change the result.
- Return a concise capability warning when the chosen surface cannot perform the request.
- Provide diagnosis, explanation, or variants when explicitly requested.

## Workflow

### 1. Classify the operation

Choose exactly one:

- `generate`: text-to-video from a new idea.
- `first_frame`: animate an image as the literal starting frame.
- `reference`: use images for subject, product, object, style, location, or motion guidance.
- `edit`: change an existing video or prior Omni result.
- `diagnose`: explain an unwanted output, rejection, or failure.

Creation and editing are different modes. Never apply the creation template to an edit.

### 2. Resolve the provider only when consequential

The target may be `Flow` or `Gemini API`.

- Do not ask about surface for a portable text-only creative prompt.
- Ask or infer the provider before validating duration, asset roles, edit, Avatar, voice, audio-reference, extension, or interpolation capability.
- If the user names the surface, obey its current capability contract.
- Do not solve provider differences by embedding one provider's request syntax in the authoring prompt.
- If capability materially changes and the provider is unknown, ask one short question rather than guessing.

### 3. Normalize the brief

Extract authoritative directed input as written. Normalize or complete creative direction only when the input is rough or genuinely incomplete.

Identify:

- one visible story beat or end-state;
- subject, action, environment, and opening blocking;
- single continuous shot or intentional multishot;
- audio mode;
- exact dialogue, voiceover, or on-screen text;
- asset role for every upload;
- important protected elements for edits;
- any known risk: identity, wrong speaker, complex motion, exact text, non-English speech, safety, or backend failure.

Ask only for consequential missing information:

- whether an image is a literal first frame or a loose reference;
- the surface when it changes syntax/capability;
- who speaks and the exact line;
- whether sound means dialogue, voiceover, ambience, music, or silence;
- whether edit audio must be preserved or regenerated.

Do not interrogate the user for camera body, lens, FOV, Kelvin, or numerical atmosphere settings unless their brief makes one important.

### 4. Apply defaults

- Respect the scene duration. Flow exposes selectable 4, 6, 8, and 10 second settings. The current Gemini API documents a 3–10 second output range but no duration request parameter, so duration wording is best-effort there. Never represent an API prompt duration as a guaranteed configuration. Default to 10 seconds only when duration is unspecified.
- For rough input, turn a simple event into one continuous shot.
- For rough input, use an intentional timed multishot only when the request implies cuts, montage, coverage, or sequential story beats.
- If characters should not speak and sound is unspecified, use fitting natural ambience with no dialogue, voiceover, or music.
- Preserve an already precise prompt or directed-scene contract. Repair only contradictions, missing Omni controls, weak asset roles, overloaded timing, or unsupported assumptions.

### 5. Pass the capability gate

Before writing, check current surface limitations. In particular:

- Current public API voice editing, uploaded audio references, video extension, and first/last-frame interpolation are unsupported.
- Uploaded-video editing and some inputs have regional or identity restrictions.
- Flow can expose features that the public API does not.
- Early claims that Omni lacks first-frame support are stale; current Flow/API support explicit first-frame roles.

If unsupported, do not fabricate prompt syntax. State the blocker and nearest verified alternative.

## New-generation procedure

Use the creative-direction steps below to complete rough input. For authoritative directed input, preserve the supplied decisions and perform only the model-specific translation and checks needed to express them in Omni.

### 1. Reduce the idea to a renderable beat

Translate abstract emotion into observable behavior, light, material, sound, and camera evidence. Write what visibly changes by the end of the clip.

Prefer one dominant event. If the request contains too many events, preserve the central beat and simplify secondary motion.

### 2. Stage the opening

Establish subject position, orientation, eyeline, important props, and environment geometry. Do not contradict an attached first frame.

### 3. Choose shot architecture

For a simple continuous event, use natural wording such as:

```text
<selected-duration>-second single continuous unbroken shot. No scene cuts.
```

For deliberate cuts, use non-overlapping time ranges that begin at zero and end at the selected duration. Use them only when order or synchronization matters:

```text
[0-<cut-1>s] ...
[<cut-1>-<cut-2>s] ...
[<cut-2>-<selected-duration>s] ...
```

Never combine deliberate cuts with `No scene cuts`.

### 4. Describe action and visual control

Write concrete cause → motion → reaction. Use one coherent camera behavior per beat. Select only useful details from:

- framing and camera movement;
- environment and spatial relation;
- lighting source and visible effect;
- material and texture;
- capture character or style;
- facial and physical acting cues.

Avoid generic adjective stacks and arbitrary numeric specifications. For standard subjects, Omni's world knowledge is sufficient. For non-standard subjects — custom anatomy, non-human character designs, invented vehicles, or creatures with unusual structure — state the structural facts that world knowledge cannot supply. Do not omit these on grounds of brevity.

### 5. Add the audio contract

Choose one mode and make it explicit.

**Exact character dialogue**

```text
At [time], only [speaker] says exactly: "[short line]" in [language], [delivery]. [Listener] remains silent. No other voices. Sound design: [ambience/SFX]. [Music instruction or No music.]
```

Read the line aloud mentally and ensure it fits its time window with margin. Never write only `they talk` or `she says something`.

**Voiceover only**

```text
A single off-screen [voice] voiceover says exactly: "[line]". No character dialogue. Sound design: [ambience]. [Music instruction.]
```

For a registered project narrator, put its `@narration-*` handle exactly at the
voice source in that sentence, for example:

```text
A single off-screen @narration-kathamind voiceover says exactly: "[line]". No character dialogue.
```

`@narration-*` handles are audio-only identities resolved from project-root
`voices.json`. Do not put them in a scene's `subjects` array and never describe
or stage them as visible characters. The runtime compiler injects the resolved
voice profile once while preserving the handle in the authored prompt.

**Ambient sound only**

```text
Sound design: [specific diegetic ambience and necessary effects]. No dialogue. No voiceover. No music.
```

**Music and effects**

```text
Audio design: [genre, energy, source, and synchronization point]. [Diegetic effects]. No dialogue or voiceover.
```

**Best-effort full silence**

```text
Silent audio track. No dialogue, voiceover, music, ambience, or sound effects.
```

Google documents natural-language negatives such as `No dialogue`; positive-only prompting is not an Omni rule. Prompt-level silence does not guarantee that the generated file contains no audio stream. If literal zero audio is required, say that post-generation audio stripping is needed outside this skill.

### 6. Bind speech sources carefully

When wrong-speaker leakage is a risk:

- name the only speaker or voice source;
- quote the exact line;
- say `No other voices`;
- describe visible listeners as silent;
- add `lips remain closed` only when the known failure justifies it, as a best-effort heuristic.

Do not place intelligible TV/radio speech beside an on-screen listener unless the distinction is essential. Use indistinct nonverbal broadcast murmur when words are unnecessary.

### 7. Handle on-screen text

Quote every intentional sign, caption, lower third, label, or license plate exactly. Keep critical copy short and visible long enough to inspect. Use `No on-screen text or captions` only when unwanted text is a real risk.

Exact text remains a known limitation. Recommend visual verification or post-production for legal copy, prices, URLs, and brand spelling.

### 8. Add only relevant negatives

Use a short, problem-specific set. Valid Omni controls include:

- `No dialogue.`
- `No voiceover.`
- `No music.`
- `No extra sound effects.`
- `No scene cuts.`
- `No on-screen text or captions.`
- `No other voices.`

Do not repeat negatives, capitalize them aggressively, or build a defensive wall that conflicts with the requested scene.

## Asset roles

Give every upload one primary role: `first frame`, `subject`, `product/object`, `style`, `location`, or `motion` reference.

In project authoring prompts, keep registered characters as `@handles` and describe any non-character asset role in natural language. Keep provider, aspect ratio, reference paths, continuity-frame selection, and authoritative duration metadata outside the prompt. Duration wording and timecodes inside the prompt express creative pacing only.

At request time, the provider adapter performs the binding:

- Gemini API: ordered media inputs, `<FIRST_FRAME>` and `<IMAGE_REF_N>` tags where needed, `video_config.task`, and response aspect ratio.
- Flow: uploaded media IDs or Flow `@AssetName` references plus Flow's duration and aspect controls.

Do not make the stored authoring prompt imitate either transport. If the user explicitly asks for a standalone copy-paste prompt outside the project pipeline, use the selected surface's current native syntax.

For a standalone current API prompt:

- use `<FIRST_FRAME>` for the literal starting image;
- use `<IMAGE_REF_0>`, `<IMAGE_REF_1>`, and so on for references, indexed from zero;
- for complex cases, declare sources/references and end with a plain-language role instruction.

Example structure:

```text
[# Sources <FIRST_FRAME>@Image1] [# References <IMAGE_REF_0>@Image2]
[Prompt]. Use Image1 as the literal starting frame. Use Image2 only as the subject reference, not as the initial frame.
```

For standalone Flow use, use platform-native `@AssetName` references only when the asset names or surface context are known.

Prefer clean, high-resolution and compatible references. Avoid unintended people or objects in style/location references. State the identity traits that must remain stable, but never promise a perfect identity lock. When multiple references share a visual class (e.g., stylized anthropomorphic characters, cartoon animals), also state the traits that distinguish each subject from the others — contrastive anchors matter more than absolute description in co-reference scenes.

## Production guardrails

### Multishot subject co-presence

In multishot prompts where multiple characters share a vehicle, room, or frame, every timed bracket must explicitly mention every active character's position or state. The model despawns entities not named in a bracket.

### Handheld prop budget

Assign at most one active item per hand (two total) in any single shot or timed bracket. When a character switches tools, drop the previous item from the description. Overloading causes frame-to-frame prop morphing.

### Stylized-world crowds

In non-human or stylized worlds, never use bare collective nouns (`crowd`, `villagers`, `onlookers`). Qualify extras with the world's anatomy (e.g., `gathered crowd of stylized vegetable villagers with assorted produce heads`). When a reference character stands near a crowd, state its exact count (`exactly one @handle`) to prevent the reference embedding from cloning onto adjacent extras.

### Prop numeracy and wearable anchoring

- For 1–4 discrete items, state the exact count.
- For 5 or more similar items, describe aggregate geometry or density (e.g., `dense cluster of slender brass tubes`) instead of a large integer. Keep large numbers strictly inside quoted dialogue.
- For loose garments or accessories that could migrate (scarves, cloths, goggles, hats), state the resting anatomical anchor (e.g., `red cloth draped around neck`).

## Video-edit procedure

Use one surgical change plus protected elements:

```text
[Make one specific visible change]. Keep [critical protected elements] unchanged. Keep everything else the same.
```

Rules:

1. Make one change per turn unless two changes are inseparable.
2. Do not re-describe the whole video.
3. For a visual-only edit, explicitly preserve original speech and audio.
4. Name only high-cost protected elements such as identity, movement, camera, lighting, timing, background, and audio.
5. Do not promise existing-speech replacement on the current API.
6. If fresh audio requires stripping the original audio stream, identify that as a workflow step outside prompt writing.

Example:

```text
Change only the red umbrella to matte black. Keep the person's face, clothing, movement, camera, lighting, background, timing, and original audio unchanged. Keep everything else the same.
```

## Duration and pacing

- Prefer one dominant event or reveal.
- Use a few readable beats only when sequence matters.
- Give exact dialogue its own time window.
- Leave a brief settled ending when the last word, pose, or product view must register.
- Avoid stacking many sequential verbs inside one short range.
- For multishot continuity, carry only essential background detail, object count, and state. Never omit the positional state of active characters — every timed bracket must account for every character who is present in the scene, even if they are not the focal actor.

These are creative heuristics, not guaranteed model laws.

## Known-risk handling

- **Complex action:** reduce to one readable cause → contact → reaction; specify real-time speed only when useful. Complex motion remains a documented limit.
- **Identity-critical scene:** prefer one clean subject reference, compatible supporting references, a true first frame when geometry matters, and a continuous shot when possible.
- **Non-English speech:** direct in English, state the language, quote a short exact native-script line, and prohibit unintended English speech. Explain that current API reliability outside English varies.
- **Critical text:** keep it short and verify it visually.
- **Literal silence:** prompt for silence but disclose that an absent audio stream requires post-processing.

## Failure diagnosis

Separate prompt failures from platform/model failures.

1. Confirm operation, surface, region, input types, and current capability.
2. For a likely false-positive safety rejection, simplify stacked cues into direct visible action and clarify adult/fictional context only when true. Attempt at most one safe rewrite. Never obfuscate words or teach filter bypass.
3. For a 99%, empty-output, or generic backend failure involving Avatar/video references, stop rewriting. Recommend a verified input/surface fallback or later retry.
4. For unwanted cuts, speech, or edit overreach, apply the targeted shot/audio/edit rule.
5. For identity drift, complex motion, exact text, speech editing, or non-English speech, explain the model limitation and offer a best-effort simplification.
6. Do not encourage repeated paid retries when evidence points to an outage, regional restriction, or unsupported feature.

## Final self-check

Before returning a prompt, verify:

- It fits the selected scene duration, defaults to ten seconds only when duration is unspecified, contains no timed event outside that duration, and does not claim API duration is a guaranteed request setting.
- Shot mode is single/no-cuts or deliberate cuts, never both.
- Audio mode is explicit and non-contradictory.
- Every spoken line has one source and exact wording.
- Silent listeners are not assigned intelligible off-screen speech.
- Every asset has one unambiguous role; standalone surface prompts use valid native syntax.
- Project authoring prompts retain `@handles` and contain no provider request configuration.
- First-frame and loose-reference roles are not conflated.
- Edit mode contains one delta and preserve clauses.
- Camera instructions can occur within the selected shot architecture.
- Critical text is exact and not presented as guaranteed.
- Identity, complex motion, silence, and non-English speech are not promised as certain.
- No unsupported or stale extension/interpolation rule appears.
- In multishot scenes, every timed bracket names every active character's position.
- No character holds more than one item per hand in any bracket.
- Crowds in non-human worlds are qualified with the world's anatomy; reference characters near crowds have explicit singular counts.
- Counts above 4 use aggregate geometry, not bare integers. Loose garments have resting anchors.
- The final response follows the requested output contract.
