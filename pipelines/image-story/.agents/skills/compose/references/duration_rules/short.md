# Short-Form (Up to Three Minutes) Rule

Treat `visual.aspect_ratio: "9:16"` with `target_duration_seconds <= 180` as project Short mode. Optimize for one complete, high-retention story unit. Do not apply these constraints to Standard or Long mode.

## Round 1 Blueprint

Generate three structurally distinct blueprints using this contract:

`SHORT — First-second hook: <first spoken words> Hook promise words: <count through the understandable promise> Hook mechanism: <reversal, consequence, impossible contrast, in-medias-res, or identity challenge> Specific question created: <one question> Payoff: <how the script answers it> Core conflict: <one conflict> Turn: <one revelation> Closing: <resolution, echo, or necessary action> Estimated spoken words: <count at or below the drafting ceiling> Tone signature: <tone>`

Choose hook mechanisms by truthful fit. Do not force all stories into the same pattern.

## First-Second Hook

Design the payoff first, then write the opening.

The hook must:

- Begin with the first spoken word; place no greeting, biography, date, or setup before it.
- Put specific tension, contrast, consequence, or an unresolved event into the first second.
- Complete its understandable promise within the first eight spoken words (roughly three to four seconds at the drafting rate). The sentence may continue after the promise lands; never damage natural syntax to hit the count.
- Make sense without prior context and create one specific question.
- Connect directly to a payoff delivered by this script.
- Stay faithful to verified research when available and otherwise remain within the user-provided premise. Never manufacture stakes or certainty.
- Treat research as optional evidence rather than a checklist. Use a verified quotation when it earns its limited runtime through authority, emotion, conflict, or payoff.

Reject generic wisdom, vague questions, and hooks that could introduce any unrelated story.

## Compression Pass

Use exactly one central promise, one conflict, one escalation chain, one decisive turn, and one takeaway or closing echo.

Assign every sentence at least one job: `HOOK`, `ADVANCE`, `ESCALATE`, `REVEAL`, or `LAND`. Delete or merge sentences with no job.

- Enter at the latest moment the story still makes sense.
- Keep only chronology and context required to understand the turn.
- Prefer concrete nouns, active verbs, short clauses, and one vivid image over explanation.
- Remove throat-clearing, duplicate facts, repeated morals, stacked adjectives, and ornamental transitions.
- Use contrast, parallelism, imagery, or echo only when they compress meaning. Be vivid, not flowery or obscure.
- End after the payoff lands. Add a call to action only when the selected blueprint needs one.
- Never use speed directions to force excess text under the limit.
- Drop optional quotes, refrains, direct-address turns, and sensory detail when they compete with clarity or the duration ceiling.

## Drafting Duration Gate

Calculate the maximum before writing:

```text
effective_seconds = min(target_duration_seconds, 170)
spoken_word_ceiling = floor(effective_seconds * 2.2)
```

This is a conservative drafting ceiling, not proof of rendered duration. Count every whitespace-delimited word in text that production will send to TTS; exclude the title, description, and prosody-direction labels.

Draft the narration, run this check, and only then persist it to `script.md`:

- The first spoken words pass the hook rules.
- The blueprint's hook-promise count matches the persisted opening, and the understandable promise lands within eight spoken words.
- The script contains only one story loop.
- Every sentence has a narrative job.
- The hook's exact promise is satisfied.
- The spoken-word count is at or below the ceiling.
- The ending is complete and was not truncated to pass.

If any check fails, compress and re-check. Do not write `script.md` or set `compose_complete` until all checks pass.

The production stage must still verify `output/final-video.mp4 <= 180.000` seconds.
