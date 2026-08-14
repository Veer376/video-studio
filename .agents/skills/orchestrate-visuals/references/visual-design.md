# Visual Design Selection

Complete this gate before character mapping or scene direction. A design is a global rendering medium for the whole video, not its setting, mood, lighting, or subject matter.

## Approved Catalog

Use only these designs unless the user explicitly requests an experiment:

| ID | Display name | Provider-neutral style prompt | Recommend when |
|---|---|---|---|
| `3d_digital_realism` | 3D digital realism | `high-end stylized 3D digital illustration, physically grounded materials and anatomy, detailed environments, expressive faces, cinematic depth, clearly computer-rendered rather than photographic` | The story needs mature action, scale, physical tension, or an epic treatment. |
| `oil_painting` | Classical oil painting | `classical figurative oil painting, visible layered brushwork and canvas texture, natural human anatomy, rich tonal modelling, painterly edges, no photographic finish` | The story needs historical, spiritual, philosophical, or adult dramatic weight. |
| `hand_painted_anime` | Hand-painted anime | `hand-painted 2D anime feature-film illustration, clean expressive linework, watercolor-gouache backgrounds, simplified natural anatomy, restrained facial design, organic painted texture` | The story is poetic, reflective, emotionally intimate, or environment-led. |
| `stylized_3d_cartoon` | Stylized 3D cartoon | `stylized 3D animated-feature illustration, appealing simplified forms, expressive readable faces, soft tactile materials, rounded shape language, polished global illumination, clearly non-photorealistic` | The story is an accessible fable, family story, or warm character-led lesson. |
| `clay_stop_motion` | Clay stop motion | `handcrafted clay stop-motion miniature, visible fingerprints and sculpting marks, practical clay figures and sets, matte earthen materials, shallow miniature depth of field, imperfect handmade construction` | The story benefits from intimate, tactile, earthy, playful, or handmade expression. |

Do not put story-specific content such as `ancient India`, `dark forest`, `sacred light`, or `psychologically intense` into `style_prompt`. Put environment, action, motivated lighting, and mood into scene direction.

Do not use studio or artist names such as Pixar or Studio Ghibli in the persisted prompt. Use the descriptive catalog language.

## Approval Gate

If `session.json` already contains both an explicitly approved `visual.style_id` and `visual.style_prompt`, preserve them unless the user asks to reconsider the design.

Otherwise:

1. Read the complete script and identify the story's dominant dramatic need.
2. Recommend one catalog design with one concrete reason.
3. Present the two strongest alternatives and make the remaining catalog choices visible.
4. Use `ask_question` or a similar user-input tool when available. Put the recommendation first and mark it recommended. If the tool limits choices, include the recommendation and two alternatives; let the user select another catalog design through its free-form option.
5. Wait for explicit selection. Do not silently choose a default or begin character and scene work.

Persist the selection in `session.json`:

```json
"visual": {
  "aspect_ratio": "9:16",
  "style_id": "oil_painting",
  "style_prompt": "classical figurative oil painting, visible layered brushwork and canvas texture, natural human anatomy, rich tonal modelling, painterly edges, no photographic finish"
}
```

## Design Changes

Changing the approved design invalidates style-dependent project-local character assets and generated scene images. Before changing an existing approved design, tell the user which assets require forced regeneration and obtain confirmation. Never overwrite them from this skill; production owns generation.
