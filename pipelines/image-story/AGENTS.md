# Image-story workflow

Read `README.md` and the selected production's authored files before acting. Use `.agents/skills/image-story/SKILL.md` to route creative work to its owning stage; `compose` owns narration writing and `orchestrate-visuals` owns visual direction.

For the primary production path, use `story-video voice-step` for narration/transcription/alignment, `produce-visuals` for visual planning/generation/state, and `render-story` for final assembly. Commands and recovery controls are defined in the README and `scripts/production/README.md`. Inspect existing artifacts before resuming, preserve runtime state, and obtain human approval at creative/continuity/review gates. Generation calls can incur provider charges.

The older `story-video run/stage illustrate/stage render` path remains for compatible legacy productions. Keep its state contract separate from the primary producer. Generated-video scene production belongs to the sibling pipeline and its own agent instructions.
