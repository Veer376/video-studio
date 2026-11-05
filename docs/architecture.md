# Architecture

The two pipelines share a repository and development provenance, not a runtime or a universal scene schema.

```text
image-story
  session + scenes + continuity
      → voice units → transcription → aligned scene/word timings
      → visual dependency graph → verified media + production manifest
      → picture / caption / narration renderer → MP4

generated-video
  story + scenes + recurring references
      → prompt/reference resolution → provider clip
      → contact sheet + human decision bound to SHA-256
      → accepted active clips → FFmpeg assembly → MP4
```

## Image story

`src/studio/` owns narration, transcription/alignment, shared adapters, and the compatibility CLI. `scripts/production/` owns the newer visual producer: immutable authored scene inputs, dependency planning, ordered references, content fingerprints, saved provider/job state, atomic output promotion, and a project writer lock. Human-approved continuity anchors bind an image hash and fingerprint.

`produce-visuals` is the primary image/optional-video command. `render-story` is the primary mixed-media renderer. It selects a completed generated clip when available or primary/continuation stills otherwise, aligns captions to inclusive word ranges, holds visual endings across pauses, and muxes narration. Its output contains no background music. `story-video voice-step` supplies the narration steps. The older `story-video run/stage illustrate/stage render` flow remains for compatible existing productions; its artifact/cache contract differs and should not be mixed into a new primary production.

## Generated video

`scripts/generate_scenes.py` compiles one selected scene with ordered image/continuity references and calls the chosen adapter. Active clips live at each scene's explicit `output_path`. Human review records live beside the scene config and bind to exact active bytes. Replacement generation archives the reviewed active clip and review evidence; restoration requires fresh review.

`scripts/render_video.py` rejects missing clips, unaccepted or stale review records, missing contact sheets, missing audio/video streams, and mismatched scene dimensions/frame rates before concatenating and encoding. Human acceptance is an authored decision, not an automated model-quality score.

## State and ownership

Keep each real production under its pipeline's ignored `work/` or `library/` directory. Authored story/scenes/session/continuity files carry creative intent. Manifests, narration units, transcription files, reviews, media, and scratch evidence carry runtime state. Back up those files together; Git tracks code and small public fixtures, not your production library. Creative skills stay under the owning pipeline's `.agents/skills/` and are read by an agent host; no particular host is required to run the documented Python commands.
