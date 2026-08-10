# Project instructions

## Required context

- Read `README.md`, `STORY_PLAN.md`, `characters.json`, and `scenes.json` before planning or generating story clips.
- Use the shared `omni-flash-prompt-writer` skill for every Gemini Omni Flash clip prompt, prompt revision, and prompt diagnosis.
- Do not use that skill for still-image character design prompts or API implementation.

## Clip pacing

- Each generated clip targets 10 seconds.
- Draft action-dense clips on the high side of what can fit: rapid cause-action-reaction, urgent physical movement, quick reactions, and deliberate cuts when the story needs them.
- Never underfill a clip with one slow action. Explicitly request real-time, immediate, decisive movement where urgency applies; do not use slow motion or lingering shots unless the story requires them.
- Urgent dialogue must be short, exact, assigned to one named speaker, and delivered rapidly in Hindi with the intended emotion.
- If a clip becomes unrenderable, remove its lowest-value insert or reaction. Preserve the central action, dialogue, and end-state hook.
- Every clip must define its opening state, visible change, and ending state so the following clip can continue cleanly.

## Visual palette

- Use light, vibrant, highly saturated, child-friendly colours when defining characters, clothing, props, lighting, and scene environments.
- Avoid boring, muddy, heavily desaturated, or predominantly dark palettes. Use dark colours only as limited contrast or when a story-critical moment requires them, while keeping the overall frame colourful and clearly readable.

## Subjects and references

- Create character reference images and `characters.json` entries only for recurring characters whose appearance must remain consistent across multiple clips.
- Do not register one-off characters, background extras, locations, or flexible story elements merely because they appear in a scene. Describe them directly in the scene prompt instead.
- Author story prompts with the semantic handles defined in `characters.json`, such as `@aloo`, `@gajar`, `@chhotu`, `@cow`, and `@jadui_bargad`.
- These `@handles` are project authoring syntax, not native Gemini API character parameters.
- Before an API call, resolve the handles in first-appearance order to the corresponding `reference_path` images and replace them with `<IMAGE_REF_0>`, `<IMAGE_REF_1>`, and so on. Do not send unresolved handles to the Gemini API.
- Keep generic background extras and non-recurring subjects unreferenced unless their exact identity later becomes important across clips.
- Use `<FIRST_FRAME>` only for a literal starting frame extracted through `reference_scene_id`. Do not confuse it with a loose subject reference.
- If a previous scene's final frame visibly drifts from a registered character reference, do not blindly preserve the incorrect face. In the next prompt, identify the drifted figure by clothing and position, keep the frame's blocking, and explicitly restore the character's defining reference traits as motion begins. Reinforce those traits in subsequent dependent clips until the corrected identity is stable.
- When a curated composite first frame already contains every required character correctly, do not stack all individual character images on top of it if testing shows duplication or identity transfer. Use the composite as the single authoritative visual source and describe each character identity explicitly in the prompt.
- Do not create or store a separate `extended_prompt`; resolve handles only at request time.

## Audio and dialogue

- Give every clip an intentional audio environment: relevant ambience, motion sounds, impacts, weather, crowd reactions, and music direction when appropriate.
- Let Omni infer incidental vocal sounds such as panting or crying unless a sound is essential to the story beat.
- Quote every spoken line exactly, identify the only speaker for its time window, and keep listeners visibly silent when speaker leakage is a risk.
- Do not add generic speech. Use `No other voices` when only one character should speak.

## Output discipline

- Store final authoring prompts in `scenes.json` using `@handles`.
- Keep `characters.json` limited to recurring, consistency-critical character identity: handle, name, and reference path.
- Save one canonical video at each scene's `output_path`. Skip existing videos by default; replace one only when regeneration is explicitly requested and the replacement has passed stream validation.
- Visually review generated clips and verify final media streams before marking a scene generated.
