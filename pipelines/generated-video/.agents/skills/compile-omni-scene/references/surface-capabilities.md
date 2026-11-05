# Surface capabilities

Gemini API documentation checked: 2026-11-05. Flow feature snapshot: 2026-08-20; verify its current product table before promising Flow-specific features.

Read this file before emitting platform-specific asset syntax or promising editing, Avatar, voice, audio-reference, extension, or interpolation behavior.

Current dated first-party documentation outranks this snapshot when behavior changes.

## Canonical model

- Model family: Google Gemini Omni / Gemini Omni Flash.
- Public Developer API model ID: `gemini-omni-1.1-flash`; the previous `gemini-omni-flash-preview` is shut down. Vertex uses its own published model IDs.
- Current API model output range: 3–10 seconds, 24 FPS; 360p/720p and upscaled 1080p/4K output are documented.
- Current API aspect ratios: `16:9` and `9:16`.
- Flow exposes selectable 4, 6, 8, and 10 second durations.
- The runtime sends `response_format.duration` as an integer-seconds string (3–10 seconds) and requests 720p. Verify actual output duration after generation; request serialization is mock-tested, account acceptance is not live-verified.

Sources:

- [Gemini Omni Flash model reference](https://ai.google.dev/gemini-api/docs/models/gemini-omni-flash)
- [Google Cloud video duration field](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-text)
- [Flow supported models and features](https://support.google.com/flow/answer/16352836?hl=en)

## Surface routing

| Need | Flow | Gemini API |
|---|---|---|
| Text-to-video | Supported | `text_to_video` |
| First-frame generation | Supported in current feature table | `<FIRST_FRAME>`, `image_to_video` |
| Image references | Ingredients/reference workflow | `<IMAGE_REF_N>`, `reference_to_video` |
| Existing-video editing | Supported subject to product/region rules | `edit`, with regional/input limits |
| Stateful editing | Product conversation/history | `previous_interaction_id` |
| Avatar/character references | Advanced Flow references | Not equivalent to Flow |
| Audio/custom voice reference | Supported Flow features | Uploaded audio reference unsupported |
| Voice editing | Flow custom-voice features vary | Unsupported |
| Video extension | Verify current Flow feature table | Documented; uploaded-video/region limits apply |
| First + last frame interpolation | Verify current Flow feature table | Documented two-image input with transition instruction |

## Project authoring boundary

`scenes.json` stores one provider-neutral authoring prompt with project `@handles`. It does not store Flow media IDs, Flow asset names, API tags, or request parameters.

The runtime adapter owns provider serialization:

| Concern | Flow adapter | Gemini API adapter |
|---|---|---|
| Duration | Select 4, 6, 8, or 10 seconds | `response_format.duration`, e.g. `4s`; measure returned output |
| Aspect ratio | Flow landscape/portrait setting | `response_format.aspect_ratio` |
| First frame | Uploaded start-media role | Ordered image input plus `<FIRST_FRAME>` when explicit binding is needed |
| References | Uploaded media IDs or Flow `@AssetName` | Ordered image inputs plus `<IMAGE_REF_N>` when explicit binding is needed |
| Operation | Flow generation/edit workflow | `video_config.task` |

Do not choose one provider's transport as the canonical prompt format. The stable contract is the authoring prompt plus separate scene metadata, compiled at request time.

Sources:

- [Gemini API Omni guide](https://ai.google.dev/gemini-api/docs/omni)
- [Flow video creation](https://support.google.com/flow/answer/16353334?hl=en)
- [Flow supported models and features](https://support.google.com/flow/answer/16352836?hl=en)

## API tasks and asset syntax

Current API `video_config.task` values:

- `text_to_video`
- `image_to_video`
- `reference_to_video`
- `edit`

Image roles:

```text
<FIRST_FRAME>
<IMAGE_REF_0>
<IMAGE_REF_1>
```

Complex role declarations:

```text
[# Sources <FIRST_FRAME>@Image1]
[# References <IMAGE_REF_0>@Image2]
```

Always add a natural-language suffix when roles could be confused:

```text
Use Image1 as the literal starting frame. Use Image2 only as a subject reference, not as the initial frame.
```

References are indexed from zero. Do not emit API tags for Flow.

## Creation versus editing

New generation benefits from useful scene, action, camera, lighting, and mood detail.

Video editing benefits from a short delta:

```text
[One specific change]. Keep everything else the same.
```

Over-describing an edit can change unrelated identity, lighting, scene, motion, or audio.

## Audio contract

Omni tries to infer an appropriate audio track by default. Normal-prompt negatives are supported and recommended:

- `No dialogue.`
- `No extra sound effects.`
- `No embellishments.`
- `No scene cuts.`
- Official examples also use `No music` and `No voice cuts at the end`.

The API does not expose a separate negative-prompt parameter. Put relevant negatives in the regular prompt.

Google documents no mandatory dialogue markup grammar. Exact speaker, quoted line, delivery, language, and timing are natural-language controls, not guarantees.

## Single-shot behavior

Omni attempts several shots by default. Current recommended controls include:

```text
In a single unbroken scene.
In a single continuous shot.
No scene cuts.
```

Use `oner`, `static`, `locked off`, `fixed`, `push in`, `punch in`, `dolly zoom`, `natural smartphone zoom`, `film camera`, or `webcam style` when they fit. Google does not require fixed numeric FOV, speed, fog, white-balance, or camera-body blocks.

## Timing

Natural timing works:

```text
After 3 seconds ...
At 5s ...
```

Bracketed ranges also work:

```text
[0-3s] ...
[3-6s] ...
[6-10s] ...
```

No exact special syntax is required. Use timecodes only when sequence or synchronization needs control.

## Current API limits that must short-circuit prompting

As of the current guide:

- uploaded audio references are unsupported;
- video references support at most three clips of up to three seconds each; reference audio is ignored;
- multiple-video reasoning is unsupported or degrades output;
- uploaded-video extension is limited to appending and has input/region/dialogue constraints;
- voice editing is unsupported;
- system instructions, temperature, `top_p`, stop sequences, and a separate negative-prompt parameter are unsupported;
- YouTube URLs are unsupported as media sources;
- uploaded-video editing has regional restrictions;
- recognizable-person and minor-related input restrictions apply in some contexts.

Service capabilities do not imply that every operation is exposed by this repository's scene runner. The primary public template uses text-to-video; inspect adapter support before planning editing or extension workflows.

## Language and model limitations

- English is fully supported by the current API.
- Other languages have not been evaluated and results vary.
- Complete consistency through edits, complex motion, and perfectly accurate text remain known limitations.
- Existing-speech modification is restricted and voice editing is unsupported in the public API.

Sources:

- [Gemini API Omni guide](https://ai.google.dev/gemini-api/docs/omni)
- [Gemini Omni Flash model card](https://deepmind.google/models/model-cards/gemini-omni-flash/)
- [DeepMind prompt guide](https://deepmind.google/models/gemini-omni/prompt-guide/)

## Regional and safety handling

Current regional and input restrictions can make a valid prompt fail. Check the current product page before diagnosing the wording. Never recommend VPN use, word obfuscation, or safety-filter evasion.

Sources:

- [Flow availability](https://support.google.com/flow/answer/16353544?hl=en)
- [Gemini API Omni guide](https://ai.google.dev/gemini-api/docs/omni)
