---
name: direct-video-scene
description: "Turn an approved video-scene or clip brief into a provider-neutral directing contract. Use after story intent is locked and before provider-specific prompt compilation. Own audience attention, staging, performance, cinematography, temporal construction, sound direction, continuity handoff, and precision/latitude. Do not rewrite story facts, emit provider syntax, generate media, or review rendered output."
---

# Direct Video Scene

Translate an approved scene or clip into a precise plan for **how the audience experiences it**. The story source decides what happens. This skill decides how that existing event is staged, seen, heard, timed, and handed off.

The result must be useful to any downstream implementation: generative video, deterministic motion graphics, live-action planning, or another provider. Keep the contract semantic and provider-neutral.

## Ownership boundary

- **Upstream story/brief owns:** story events, factual state, character motivation already established by the source, exact dialogue, required objects, and required outcomes.
- **This skill owns:** viewer attention, opening and ending presentation, blocking, observable performance, camera and composition, coverage, temporal structure, sound direction, continuity handoff, and which details must remain exact versus may vary.
- **Provider compiler owns:** model syntax, capability limits, reference binding, first/last-frame mechanisms, task modes, provider-specific mitigations, and prompt diagnostics.
- **Caller owns:** persistence, asset creation, generation, rendered-output review, retries, and final assembly.

Do not solve a downstream capability problem by quietly changing the story. If the intended direction is coherent but a provider later cannot execute it, return to this skill only to adapt the presentation within the same story facts.

## Authority model

Before directing, distinguish four kinds of information:

1. **Locked fact** — established by the approved brief, project rules, exact dialogue, or required story outcome.
2. **Observed continuity evidence** — what an inspected predecessor frame, clip, recording, layout, or approved visual actually shows.
3. **Creative grammar** — project-level visual, camera, sound, pacing, or motif rules that should shape the scene.
4. **Directorial freedom** — presentation choices not fixed by the first three.

Never turn an assumption into a locked fact. For the visible starting state of a continuing physical moment, inspected evidence outranks remembered or inferred continuity. If evidence conflicts with a locked story fact, surface the conflict instead of silently choosing one.

## Required inputs

Use the available:

- approved scene or clip brief;
- duration or timing envelope;
- intended format/canvas when composition depends on it;
- project creative grammar when present;
- exact dialogue, narration, music, or timing cues already locked;
- relevant characters, location, props, and factual state;
- adjacent-scene obligations;
- inspected continuity evidence when the clip continues an existing physical moment.

Ask only when a missing choice materially changes the scene and cannot be safely inferred from the approved context.

## Direction procedure

### 1. Establish authority and freedom

Identify what is locked, what is observed, what creative grammar applies, and what remains free to direct. Resolve or report conflicts before designing shots.

### 2. Define the audience intention

State:

- **first read** — what the viewer should notice first;
- **dominant development or hold** — what changes, becomes clear, or is deliberately sustained during the clip;
- **end impression** — what the viewer should be left attending to or feeling.

Do not force every short clip to contain its own dramatic arc. A clip may only complete a reaction, continue an action, hold tension, establish geography, or deliver one piece of information.

### 3. Lock boundary states before camera design

Read [references/continuity-and-control.md](references/continuity-and-control.md).

Define the relevant opening state and the consequential ending state before choosing coverage. Include only state that affects presentation: position, orientation, eyeline, ongoing motion, prop state, environment, audible state, and any intentional discontinuity.

### 4. Stage the event

When people, creatures, objects, interfaces, or physical interactions change state, read [references/performance-and-blocking.md](references/performance-and-blocking.md).

Establish readable spatial relationships, paths, entrances/exits, screen direction, eyelines, contact, reactions, and prop handling. For characters, use playable behavior rather than generic emotional labels. Add objectives, tactics, listening tasks, breath, business, or proxemics only when they materially improve the scene.

### 5. Resolve cinematography and coverage together

Read [references/cinematography.md](references/cinematography.md) and [references/coverage-and-timing.md](references/coverage-and-timing.md).

Choose framing, viewpoint, composition, focus, camera position, camera behavior, cuts, and visual progression because they control information and attention. Static is valid. A camera move must have a reason and a meaningful destination.

Do not design camera motion independently of blocking. The chosen view must preserve the spatial relationship and action the audience needs to read.

### 6. Direct sound when it affects the experience

Read [references/sound-direction.md](references/sound-direction.md) whenever speech, synchronized effects, ambience, music, silence, or an audio bridge matters.

If locked dialogue, narration, music, or a sound cue determines timing, treat it as an input to visual timing rather than adding it after the shot is designed.

### 7. Integrate everything on one timeline

Build one temporal plan. Each interval may contain:

- **view** — framing, composition, focus, and spatial relationship;
- **events** — action, performance, object/state change, or held state;
- **camera** — position, movement, or deliberate stillness;
- **sound** — speech, cue, ambience, music, or silence;
- **transition** — only when a cut or handoff occurs.

Use exact timestamps only when order, synchronization, reading time, dialogue fit, or a hard cue requires them. Otherwise use coarse phases such as opening / development / landing.

The timeline is the integration point. Do not return separate camera, performance, and sound plans that contradict one another.

### 8. Set precision, latitude, and control needs

Separate:

- **must remain exact** — details whose change would break story, continuity, identity, geography, timing, or the intended viewer effect;
- **may vary** — details whose variation does not change the meaning of the shot;
- **control/previs dependency** — a relationship that should be visually or temporally anchored before execution because prose alone is too ambiguous.

State the dependency semantically, for example `opening geometry must be visually anchored` or `the hand-to-object contact needs a clear key pose`. Do not prescribe a provider mechanism such as first-frame generation or a reference token.

### 9. Run the density and coherence gate

Before returning the contract, verify:

- the intended events can register within the available duration;
- dialogue and reaction have enough time to be understood;
- the final state is physically and temporally reachable;
- camera movement does not hide the important action;
- simultaneous actions do not compete for the same viewer priority unless that competition is intentional;
- spatial relationships and screen direction remain coherent;
- important cause → movement → consequence is readable;
- the ending image/state is deliberate rather than accidental.

Simplify discretionary direction before weakening a locked story requirement. When overloaded, identify the lowest-value removable directorial element.

## Output contract

Return a **minimum complete contract**, not a maximum-filled form. Omit inapplicable fields.

```markdown
## Directed scene

### Authority
- Locked facts:
- Continuity evidence:
- Creative grammar:
- Directorial freedom:

### Envelope
- Duration:
- Canvas / format:

### Audience intention
- First read:
- Dominant development / hold:
- End impression:

### Boundary states
- Opening state:
- Ending state:
- Handoff:

### Staging
- Spatial relationships:
- Subject paths / screen direction:
- Performance or subject behaviour:
- Critical props / contact:

### Timeline
- <span or phase>
  - View:
  - Events:
  - Camera:
  - Sound:
  - Transition: <only when applicable>

### Visual treatment
- Composition / focus:
- Environment / lighting:
- Scene-specific treatment:

### Audio
- Speech / voice:
- Synchronized sound:
- Ambience / music / silence:
- Priority / bridge:

### Precision and latitude
- Must remain exact:
- May vary:
- Control / previs dependency:
- Remove first if overloaded: <omit when none>
```

Do not repeat the same fact in several sections. If the timeline already fully expresses a simple shot, keep the other sections terse.

## Invariants

- Story facts are immutable here; direction changes presentation, not events.
- One dominant viewer priority should exist at any instant unless intentional ambiguity is itself the effect.
- Opening state must be explicit when continuity matters.
- Ending state must be intentional and usable as a handoff when another clip depends on it.
- Important physical action must expose readable cause, movement/contact, and consequence.
- Camera movement must change information, relationship, scale, tension, or attention; otherwise stillness is valid.
- Characters respond to stimuli and pursue playable behavior rather than merely displaying named emotions.
- Spatial relationships, eyelines, object ownership, and screen direction may not contradict themselves.
- Exact dialogue remains exact.
- The plan must fit the actual duration.
- Must-hold decisions must be distinguished from creative latitude.
- Inspected evidence outranks assumptions about current visible state.
- Control/previs needs must be surfaced rather than hidden.
- No provider syntax, provider capability claim, API reference, or generation mechanism enters this contract.

Unless the user asks for alternatives or explanation, return only the selected directed-scene contract.
