# Story planning

Use this reference only when creating or revising `story.md`.

## Establish the creative contract

Capture only decisions that materially affect clip creation:

- premise and intended audience;
- target runtime and clip duration;
- genre and visual treatment;
- pacing and action density;
- dialogue language and style;
- colour and lighting direction;
- audio character;
- recurring themes or story-wide restrictions.

Ask about a missing choice only when different answers would materially change the story.

## Persist story-writing instructions

When initializing `story.md`:

1. Synthesize concise, story-specific writing instructions from the user's direction and approved creative decisions.
2. Keep only rules that must guide multiple future parts, such as pacing, clip progression, part construction, and overload handling.
3. Present the instructions with the macro structure for approval.
4. Before drafting or revising each part, reread and apply the current creative contract and story-writing instructions.
5. When the user changes a persistent direction, update `story.md` before continuing.

Do not invent generic model rules or copy instructions from another story.

## Structure the story

Use the canonical `story.md` structure in [artifact-contracts.md](artifact-contracts.md). The macro table and detailed parts must agree: every macro part appears as one part section, and every allocated clip appears exactly once with contiguous timestamps.

Do not store final Omni prompts, API syntax, output paths, or generation logs in `story.md`.

## Design renderable clips

- Give every clip an opening state, one dominant visible development, and an ending state that advances the story.
- Use timed beats only when order, synchronization, or dialogue timing matters.
- Keep dialogue inline in the clip brief; do not create separate dialogue metadata.
- Allocate part boundaries in multiples of the configured clip duration.
- Give every part one clear purpose, entry state, exit state, duration, and clip allocation.
- Make each part's entry state follow the previous part's exit state unless the transition is explicitly defined.
- If a clip is overloaded, identify its essential beat and the lowest-value removable beat.
- Follow the selected story's creative contract; do not import style rules from another story.

Present the planned scope for approval before producing prompts unless the user explicitly authorized continuous planning and production.

Before prompting a part, persist its approved briefs and story-wide changes in `story.md`.
