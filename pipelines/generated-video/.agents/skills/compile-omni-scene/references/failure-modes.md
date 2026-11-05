# Failure modes and targeted responses

Last reviewed: 2026-08-16.

Use this file for diagnosis. Do not turn every workaround into mandatory prompt boilerplate.

Evidence labels:

- **Verified:** current Google documentation/model card.
- **Corroborated:** repeated reports aligned with official behavior.
- **Experimental:** plausible community workaround requiring A/B tests.
- **Stale/rejected:** contradicted by current docs or unsupported as a general rule.

## Quick classifier

| Symptom | Likely class | First response |
|---|---|---|
| Unwanted speech, music, effects, or cuts | Prompt omission | Add one targeted audio/shot contract. |
| Unrelated content changes during an edit | Prompt over-description + model consistency | Reduce to one delta and preserve clauses. |
| Reference ignored or identity drifts | Model limit + ambiguous/competing assets | Clarify one role per asset and simplify references. |
| Action floats, slows, or misses contact | Known complex-motion limit | Simplify to one cause → contact → reaction. |
| Text misspelled | Known exact-text limit | Shorten, quote, expose longer, verify/post-process. |
| Hindi becomes English | Unevaluated language reliability | English direction + exact Devanagari line + warning. |
| Policy rejection on benign content | Possible safety false positive | Check eligibility; one safe rewrite; then stop. |
| 99%, empty output, or generic Avatar/video-ref failure | Platform/input/outage | Stop prompt rewriting; change input path or retry later. |
| Feature cannot work in the public API | Capability | Return blocker and verified alternative. |
| Character vanishes in one multishot bracket | Per-bracket entity despawning | Name every active character in every timed bracket. |
| Prop morphs between frames | Handheld overload | Limit to one item per hand; drop inactive props. |
| Reference character cloned onto crowd extra | Embedding bleed into ambiguous silhouettes | Qualify crowd anatomy; add `exactly one @handle`. |
| Large item count collapses; garment migrates to wrong body part | Numeracy limit + anatomical ambiguity | Use aggregate geometry for 5+; anchor loose garments. |

## 1. Unwanted character speech

Confidence: **corroborated**, with an official audio-default explanation.

Response:

```text
Sound design: [exact ambience]. No dialogue. No voiceover. No music.
```

If only voiceover should speak:

```text
A single off-screen narrator says exactly: "...". No character dialogue. No other voices.
```

For a recurring wrong speaker, describe the listener as silent and optionally say `lips remain closed`. Treat that phrase as experimental, not guaranteed.

## 2. Unwanted cuts or camera changes

Confidence: **verified default**.

Response:

```text
<selected-duration>-second single continuous unbroken shot. No scene cuts.
```

Add one coherent camera behavior. Do not combine locked-off framing with an implied cut to a different angle.

## 3. Edit overreach

Confidence: **verified**.

Response:

```text
[One visible change]. Keep [high-cost protected elements] unchanged. Keep everything else the same.
```

For visual-only edits, protect original speech and audio explicitly. If speech still changes, classify it as a model/capability limit rather than adding a long wall of instructions.

## 4. Identity or reference drift

Confidence: **verified model limitation + corroborated reports**.

Mitigations:

- assign one primary role to every asset;
- use a true first frame when opening geometry matters;
- prefer clean high-resolution subject/product references;
- remove unintended people or objects from style/location references;
- keep reference lighting and visual language compatible;
- use one continuous shot when continuity is critical;
- state a small number of visible identity traits that must remain.

Do not claim perfect identity or character locks.

## 5. Object count or continuity drift

Confidence: **corroborated**.

Mitigations:

- reduce entities and cuts;
- state the exact count once;
- carry only essential object state between timed shots;
- prefer one continuous shot for critical object permanence;
- split elaborate stories into separate clips.

## 6. Complex or contact motion

Confidence: **verified model limitation + corroborated symptoms**.

Mitigation:

Describe one visible cause → contact → reaction at real-time speed. Reduce simultaneous choreography. `Smooth motion` or `real-time speed` may help but remains a best-effort heuristic. Never promise that prompting removes the documented limitation.

## 7. Duration truncation or front-loaded dialogue

Confidence: **community evidence + official timing controls**.

Mitigations:

- keep one dominant event;
- give exact dialogue a non-overlapping time range;
- read the line aloud for fit;
- leave a brief settled end-state when closure matters;
- avoid many sequential verbs in one range.

The end buffer is a creative heuristic, not a formal Omni requirement.

## 8. Dialogue editing failure

Confidence: **officially restricted/unsupported + repeated reports**.

Do not promise replacement of existing speech. For a visual edit:

```text
Keep the original speech and audio unchanged. Keep everything else the same.
```

For new words, offer a fresh generation or an external audio/post-production workflow when appropriate.

## 9. Non-English dialogue

Confidence: **official caveat + limited community evidence**.

Use an English directing wrapper:

```text
Spoken language: Hindi (India). Only Asha says exactly: "हम घर पहुँच गए।" No English speech or voiceover.
```

Keep the line short. Disclose variable output; do not claim the prompt guarantees language adherence.

## 10. Exact on-screen text

Confidence: **verified model limitation**.

Specify one short quoted string, its script/language, location, and exposure. Verify the result. Use post-production for legal copy, prices, URLs, or brand spelling that must be exact.

## 11. False-positive safety rejection

Confidence: **repeated reports; no universal workaround**.

1. Check the target surface, region, input type, and current policies.
2. Confirm the request is legitimately allowed.
3. If the scene stacks ambiguous distress/age cues, rewrite them as direct visible action and clarify adult/fictional context only when true.
4. Attempt at most one safe rewrite.
5. Preserve the prompt/job details and use support/reporting if it still fails.

Never obfuscate words, disguise intent, or teach safety bypass.

## 12. Avatar/video-reference failure at 99%

Confidence: **repeated platform/outage pattern**.

Do not expand or repeatedly mutate the prompt. Check whether image-only succeeds, remove the affected Avatar/video input as a disclosed fallback, switch to a verified supported surface, or retry later. Record job and billing details.

## 13. Failed generation consumes credits

Confidence: **inconsistent reports**.

Treat as billing/platform behavior. Avoid repeated paid retries, record prompt/time/surface/job ID, and use the product support path.

## 14. Regional restriction

Confidence: **verified, volatile**.

Check current product/API documentation. Do not repeat stale India restrictions and do not recommend VPN workarounds.

## 15. First-frame unavailable

Confidence: **stale/rejected**.

Current Flow/API documentation supports explicit first-frame roles. Correct the asset binding instead of teaching that Omni cannot use a first frame.

## 16. Fixed prompt-length or technical-block rules

Confidence: **rejected as universal**.

Do not enforce 20–50 words, a fixed 15-block structure, mandatory FOV, km/h, fog percentage, Kelvin, or positive-only language. Use enough non-conflicting detail for a new generation and deliberately short prompts for edits.

## 17. Multishot subject dropout

Confidence: **corroborated**.

In multishot prompts with timed brackets (`[0-4s]`, `[4-8s]`, etc.), the model evaluates entity presence per bracket. Characters not explicitly named in a bracket are despawned from the frame, even if declared in `subjects`. This causes empty driver seats, vanishing co-passengers, and ghost vehicles.

Mitigation: every timed bracket must explicitly state the position or background presence of every active character. For shared vehicles, name driver and passenger in each cut.

## 18. Handheld prop overload and morphing

Confidence: **corroborated**.

Assigning more than one active item per hand in a single shot causes the model to morph props frame-to-frame (e.g., cane → hammer, wrench → steering wheel). The model cannot resolve biomechanical contact for multiple simultaneous handheld objects.

Mitigation: maximum one active item per hand. When a character switches tools, drop the previous item from the character's descriptor in that bracket. Strip attire accessories (canes, lanterns) when action tools (hammer, wrench) are in use.

## 19. Crowd subject cloning

Confidence: **corroborated**.

When a reference-image character stands near background crowd extras without explicit singular constraints, cross-attention applies the reference embedding to adjacent humanoid silhouettes, duplicating the character.

Mitigation: state `exactly one @handle` when placing a reference character near crowds. In non-human or stylized worlds, qualify crowd anatomy explicitly (e.g., `background villagers are generic stylized extras distinct in appearance from @handle`).

## 20. Numeracy collapse and wearable misplacement

Confidence: **corroborated**.

Large integer counts (e.g., `54 rockets`, `108 tubes`) collapse to 4–5 oversized approximations. Loose garments and accessories (scarves, cloths, goggles) migrate to whichever body part the active verb implies (e.g., `wiping sweat` pulls a neck cloth to the forehead).

Mitigations:

- Use exact counts only for 1–4 items. For higher quantities, describe aggregate density or geometry instead of a number.
- Keep large numbers strictly inside quoted dialogue, not in visual descriptions.
- State the resting anatomical anchor for loose garments (e.g., `draped around neck`, `pushed up on forehead`).

## Primary evidence

- [Gemini API Omni guide](https://ai.google.dev/gemini-api/docs/omni)
- [Gemini Omni Flash model card](https://deepmind.google/models/model-cards/gemini-omni-flash/)
- [DeepMind prompt guide](https://deepmind.google/models/gemini-omni/prompt-guide/)
- [Google developer forum: serious workflow issues](https://discuss.ai.google.dev/t/omni-flash-video-generation-is-currently-not-usable-as-a-serious-creative-workflow-tool/146264)
- [Google developer forum: Avatar failures](https://discuss.ai.google.dev/t/google-ai-flow-video-generation-fails-with-oops-something-went-wrong-when-using-avatar-with-omni-flash-model/173328)
