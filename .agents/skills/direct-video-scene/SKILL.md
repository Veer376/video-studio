---
name: direct-video-scene
description: "Turn an approved rough video-scene brief into a model-agnostic directed-scene contract covering shot design, staging, performance, sound, and continuity. Use before provider-specific prompt writing or when the user wants to co-direct a scene. Do not use to invent story events, write model prompts, generate media, or review rendered clips."
---

# Direct Video Scene

Convert a rough narrative scene into a precise, filmable direction brief. Decide how the audience experiences the existing story beat; do not rewrite what happens.

## Ownership boundary

- The source brief owns story events, character motivation, factual state, and exact dialogue.
- This skill owns viewer focus, shot architecture, composition, blocking, performance, environmental motion, sound direction, and continuity handoff.
- A provider-specific prompt skill owns model syntax, capability limits, reference binding, and prompt diagnostics.
- The caller owns persistence, generation, review, retries, and rendering.

Preserve the source brief. If its content cannot fit the available duration, identify the essential beat and the lowest-value removable material instead of silently changing the story.

## Direction mode

Use `autonomous` mode unless the user explicitly asks to co-direct, explore choices, or remain involved.

In `interactive` mode:

- Use `ask_question` when available; otherwise ask concise questions in chat.
- Ask only about unresolved creative choices whose answers materially change the scene.
- Batch related choices and offer two or three concrete options described by their viewer effect.
- Recommend one option when there is a defensible choice.
- Do not ask the user to supply filmmaking terminology; translate their intent into direction.

Keep the selected mode for the active task until the user changes it. In autonomous mode, make and state the directing decisions without routine confirmation.

## Required inputs

Use the available:

- rough scene brief and exact duration;
- story-wide creative contract;
- adjacent-scene entry and exit states;
- characters, location, props, and dialogue already established;
- inspected visual continuity evidence when the scene must begin from existing footage or a curated frame.

Do not invent missing story facts. Ask only when a missing decision is consequential and cannot be safely inferred from the approved context.

## Direction procedure

### 1. Lock the narrative beat

State the scene's dramatic function, what the viewer should notice first, and what visibly or emotionally changes by the end. Preserve exact dialogue and required actions.

### 2. Design the shot

Read [references/shot-design.md](references/shot-design.md). Choose framing, angle, composition, camera behaviour, and any deliberate cuts because they serve the beat. Define an intentional opening image, visual progression, and ending image.

### 3. Stage visible performance

When characters, creatures, or physical interaction are present, read [references/performance-and-blocking.md](references/performance-and-blocking.md). Establish positions, orientations, eyelines, entrances or exits, motivated gestures, reactions, and prop handling. Express action as readable cause, movement, and response.

### 4. Direct sound and continuity

When sound, dialogue, or adjacent-scene continuity matters, read [references/sound-and-continuity.md](references/sound-and-continuity.md). Assign speech, synchronized effects, ambience, music or intentional silence. Define the incoming state that must be respected and the outgoing state the next scene inherits.

### 5. Check density

Ensure the action, dialogue, camera movement, and cuts can be understood within the duration. Keep simultaneous actions only when their relationship is important. Flag optional material rather than compressing everything into unreadable motion.

## Output contract

Return one directed-scene contract in this structure:

```markdown
## Directed scene

- Dramatic function:
- Viewer focus:
- Duration:
- Narrative change:
- Continuity in:
- Shot architecture:
- Opening image:
- Beat progression:
- Blocking and performance:
- Camera and composition:
- Visual treatment:
- Environment and lighting:
- Dialogue and delivery:
- Sound direction:
- Ending image:
- Continuity out:
- Essential constraints:
- Remove first if overloaded: <omit when none>
```

Use concrete, observable direction. Omit `Dialogue and delivery` when nobody speaks. Do not emit provider syntax or a generation prompt. Unless the user asks for alternatives or explanation, return only the completed contract.

## Final check

Before returning, verify that:

- every directing choice supports the dramatic function;
- opening positions and outgoing states are unambiguous;
- visible action has motivated cause and reaction;
- dialogue remains exact and has a clear speaker, listener state, and delivery;
- sound is tied to the setting or action rather than added as decoration;
- the scene fits its duration;
- no provider-specific capability, syntax, or guarantee has entered the contract.
