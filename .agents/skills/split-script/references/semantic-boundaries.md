# Semantic Visual Boundaries

## Governing Question

Ask: **When must the picture change for the visual narration to remain truthful?**

Create a boundary when one or more of these materially changes:

- dominant visible action or consequential state
- active subject, speaker, or character constellation
- location, time, or physical environment
- important object, ownership, condition, or spatial relationship
- character goal, decision, cause, or consequence
- information revealed to the audience

A change is material when retaining the previous image would become false, premature, confusing, or unable to depict the narrated beat.

Do not create a boundary merely because a sentence ended, a fixed number of words elapsed, or the narration changes tone while the visible situation remains stable.

Every boundary carries a burden of proof: the next span must support a materially different image grounded in its own words or in an already established visual state. If the two resulting image descriptions would be substantially the same, merge them. A discourse role such as hook, explanation, lesson, or conclusion is not sufficient by itself.

For a Short, audit the opening sentence as a possible first-frame transaction. Keep it separate when it supplies a concrete contrast, startling object, result, or question whose strongest composition is incompatible with the chronological setup that follows. Merge it when both spans genuinely support the same image. Do not let visual economy bury a narration-grounded hook inside a long setup tableau.

## Pass 1 — Candidate Boundaries

Read the narration as a sequence of events, not sentences. Mark every plausible picture-change point. Prefer sentence and paragraph boundaries, but allow a boundary at a comma, semicolon, dash, or conjunction when both sides describe sequential visual states that cannot coexist in one still.

Never split inside a noun phrase, an incomplete dependent clause, an indivisible action, or a short utterance. Preserve the connector and punctuation with their original text.

## Pass 2 — Visual Economy

For every candidate span, state its dominant visible situation internally:

```text
subject + action/state + relevant object/relationship + place/time
```

Then audit the full sequence:

- **Split** when a span asks one image to show before and after, departure and return, question and later answer, hidden and revealed information, or another incompatible sequence.
- **Merge** when adjacent spans share the same subject, action/state, place, time, and reveal level and one image remains truthful for both.
- **Absorb a brief transition into its endpoint** when the following tableau truthfully establishes that the transition has completed. Assign the transition text to the endpoint/aftermath scene, not to an incompatible origin action: a short arrival may join speech at the destination, and a departure may join the observer's resulting reaction. Do not manufacture a flash-length travel scene merely to illustrate the verb.
- Keep a long span when its stable image accumulates tension or supports an abstract reflection.
- Keep a short decisive beat separate only when it creates a meaningful visible change and remains alignment-safe.

## Special Cases

### Multi-action sentences

Separate sequential actions when one still cannot show them honestly. Actions that occur simultaneously or form one indivisible gesture may remain together.

### Dialogue and quotations

A speaker turn is a strong candidate, not an automatic cut. Keep a brief exchange together when one tableau can depict it and no later reaction is revealed early. Split when the speaking subject, listener reaction, power relationship, or visual state changes.

Keep an immediate question and answer about the same object in one tableau when the answer only completes the exchange. Separate the answer when it is itself the decisive hidden-to-revealed beat on which the story turns.

Keep short quotations intact. Split a long quotation only at a complete rhetorical clause or change of claim. Preserve and repeat the current `> ` display marker for quote continuations.

Keep an attribution such as “X says” with the quotation it introduces. Preserve the quoted-to-unquoted transition before later narration; do not let a quote marker extend across the narrator's conclusion.

### Abstract narration

Use an established reaction, consequence, object, environment, or motif as the visual state. Continue holding it while the argument remains on the same concrete referent and emotional position. Split when the example, consequence, stance, or referent changes.

A contrast or moral pivot can justify a boundary only when the new clause supplies a distinct, depictable subject, action, object, consequence, or established motif. Broad ideals such as goodness, freedom, success, or service do not become concrete merely because they are named. Attach a warning or broad prescription to the established teaching/consequence tableau when a separate image would require inventing generic examples. Do not manufacture an inspirational closing image merely because the script is ending.

Addressing the audience after a character's realization is a discourse change, not a visible-subject change. Continue the established consequence tableau unless the audience-facing passage introduces its own concrete example, object, action, or previously established motif that supports a genuinely different composition.

### Lists and comparisons

Do not create one image per list item automatically. Split only when the items require materially different visible situations. Avoid asking a single still to become a collage of unrelated examples.

## Alignment Guardrails

- Allow a single-scene script.
- Give each scene at least three speakable whitespace-delimited words unless it is the only scene.
- Treat more than 30 words as a review signal, not an automatic split.
- Use word count only for alignment safety and hold-length review; it never determines the desired scene count.

Before aligned audio exists, use `session.json` target duration only as a pacing estimate:

```text
estimated hold = scene spoken words × (target duration / total spoken words)
```

For a long-form scene estimated above roughly 15 seconds, enumerate its complete sentence/clause boundary candidates before retaining it. Split when two viable halves have different narration-grounded focal purposes—such as environment then subject, movement then address, observation then speech, quotation then application, or action then consequence—and each supports a materially different composition. A stable location or character constellation does not defeat such a cut. Retain the long scene only after every viable candidate would repeat the same focal subject, action, object, and reveal level. Never cut toward a duration quota.

Actual duration is known only after narration alignment. After alignment, review scenes with zero assigned words, unexpectedly short holds, or holds above roughly 15 seconds. Adjust a boundary only when the resulting sequence is more truthful or gains a distinct narration-grounded composition without invented coverage.
