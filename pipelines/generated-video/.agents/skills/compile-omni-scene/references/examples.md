# Prompt examples

These examples demonstrate structure, not magic wording. Adapt them to the user's scene and surface. Return one prompt only unless variants were requested.

## 1. Ambient-only continuous shot

```text
10-second single continuous unbroken locked-off medium shot of an elderly potter at a sunlit workshop table, slowly shaping a small clay bowl while fine dust catches the warm side light. His hands move steadily; he glances at the rim, makes one careful correction, then holds the finished shape still for the final second. Natural terracotta texture, quiet documentary realism. Sound design: soft wheel hum, fingertips against damp clay, faint birds outside. No dialogue. No voiceover. No music. No scene cuts. No on-screen text or captions.
```

Why it works: one beat, stable blocking, one camera behavior, observable acting, a settled ending, and an explicit audio contract.

## 2. One exact spoken line

```text
10-second single continuous handheld medium shot in a quiet railway compartment at dawn. Mira sits by the window as fields slide past; the camera makes a slow natural push-in while she watches her reflection. [4-7s] Only Mira says exactly, "I thought I had more time," in a low controlled voice, then exhales and looks outside again. No other voices. Sound design: soft rail rhythm and distant carriage rattle. No music. No scene cuts. No subtitles or on-screen text.
```

Why it works: the speaker, words, window, delivery, listener state, and competing audio are resolved.

## 3. Voiceover with silent characters

```text
10-second single continuous overhead-to-medium crane movement across a small night-market stall as a baker opens a steaming bamboo basket and hands one bun to a waiting child. A single calm off-screen narrator says exactly, "Some mornings begin before the city wakes." The baker and child remain silent. No character dialogue and no other voices. Sound design: gentle market setup sounds, cloth rustle, and distant bicycle bells. No music. No scene cuts. No captions.
```

## 4. Best-effort full silence

```text
10-second single continuous unbroken macro shot of a drop of black ink spreading through a clear glass of water against a plain white background. The camera remains fixed as delicate branching tendrils expand in real time and settle into a soft cloud during the final second. Silent audio track. No dialogue, voiceover, music, ambience, or sound effects. No scene cuts. No on-screen text.
```

If the user needs a file with no audio stream, add a separate warning outside the prompt that post-processing is required.

## 5. Intentional three-shot sequence

```text
10-second premium watch reveal with three deliberate shots. [0-3s] Extreme macro of condensation sliding over the brushed steel crown under a narrow cool rim light; only a soft low pulse begins. [3-7s] Clean cut to a slow rotating three-quarter product view on black stone, revealing the deep blue dial while one precise metallic tick lands at 5s. [7-10s] Clean cut to a stable frontal hero frame with the watch centered and motion stopped for the final second. Audio design: restrained low pulse and one precise metallic tick. No dialogue or voiceover. No extra sound effects. No on-screen text.
```

Why it works: cuts are intentional, ranges do not overlap, audio is synchronized, and the product receives a stable ending.

## 6. Standalone API first frame plus subject reference

```text
[# Sources <FIRST_FRAME>@Image1] [# References <IMAGE_REF_0>@Image2]
10-second single continuous unbroken tracking shot beginning exactly from <FIRST_FRAME>. The cyclist matching the subject identity and clothing in <IMAGE_REF_0> pushes off from the wet curb in Image1 and accelerates smoothly down the same narrow street while the camera tracks beside her at real-time speed. Preserve the original street geometry, bicycle, weather, and lighting. Sound design: tire spray, chain movement, light rain, and distant traffic. No dialogue. No voiceover. No music. No scene cuts. Use Image1 as the literal starting frame. Use Image2 only as the cyclist's subject reference, not as the initial frame.
```

## 7. Hindi dialogue

```text
10-second single continuous medium shot in a modest family kitchen at early morning. Asha sets two cups of tea on the table and looks toward her brother by the doorway. [4-6s] Spoken language: Hindi (India). Only Asha says exactly, "हम घर पहुँच गए।" in a relieved, quiet voice. Her brother listens silently; no other voices and no English speech or voiceover. Sound design: cup touching wood, a ceiling fan, and distant morning traffic. No music. No scene cuts. No subtitles.
```

Non-English generation is best-effort under current API documentation.

## 8. Surgical visual edit

```text
Change only the coffee mug from white ceramic to transparent amber glass. Keep the person's identity, hand motion, camera, lighting, background, timing, and original audio unchanged. Keep everything else the same.
```

## 9. Edit that protects dialogue

```text
Remove only the phone from the table. Keep the original dialogue, voices, music, sound effects, timing, camera, lighting, people, and background unchanged. Keep everything else the same.
```

## 10. Capability warning instead of a fake API prompt

User request:

```text
Use this MP3 as my voice reference and replace the actor's existing words through the Gemini Omni Flash API.
```

Correct response pattern:

```text
The current public Gemini Omni Flash API does not support uploaded audio references or voice editing, so prompt wording cannot perform this reliably. Use a verified Flow voice-reference workflow if available, or generate/edit the voice in a separate audio pipeline.
```

## Common repairs

| Weak or conflicting input | Repair |
|---|---|
| `A woman talks while her friend says nothing.` | Quote the woman's exact line; identify her as the only speaker; state the friend listens silently; add `No other voices.` |
| `Silent forest, with birds and wind.` | Decide between literal silence and ambient-only. Do not request both. |
| `Locked-off shot, then cut to a close-up. No scene cuts.` | Choose a continuous camera move or deliberate cuts, not both. |
| `Make it better and keep everything identical.` | Name one visible edit and a small set of high-cost protected elements. |
| `Use both images.` | Assign each image a role: first frame, subject, product, style, location, or motion. |
| `Perfectly preserve the character in a complex four-shot fight.` | Reduce cuts/action and describe stable visible traits; disclose that perfect identity and complex motion are not guaranteed. |
| `Generate exactly correct legal disclaimer text.` | Quote and simplify it, but recommend post-production for guaranteed correctness. |
