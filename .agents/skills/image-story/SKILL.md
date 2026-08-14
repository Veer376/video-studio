---
name: image-story
description: Run and resume the complete Story Video Maker project workflow, including intake, research, scene splitting, production, YouTube packaging, and YouTube publishing. Use for new image-story projects, existing library project continuation, source research, pipeline execution or status, script-to-scenes conversion, YouTube metadata or thumbnails, upload, attach, and upload-status requests. Routes focused scriptwriting and visual direction to the standalone compose and orchestrate-visuals skills.
---

# Image Story

Own the end-to-end project flow, project research, and operational stages. Keep two judgment-heavy stages separate so the agent can focus deeply:

- `compose`: blueprint approval and narration writing
- `orchestrate-visuals`: visual direction and image-prompt orchestration

## Stage References

Read only the reference required for the current stage:

| Stage | When it is needed | Read |
|---|---|---|
| Intake | No `session.json`, or the user starts a new project | `references/intake.md` |
| Research | The user chooses research before composition, or requests re-research | `references/research.md`; for Short mode also read `references/research-short.md` |
| Split | Approved `script.md` exists but `scenes.json` does not, or the user requests a re-split | `references/split-script.md` |
| Production | Run, resume, inspect, retry, voice, illustrate, render, or verify output | `references/pipeline.md` |
| Package | Create YouTube titles, description, hashtags, metadata, or thumbnails | `references/package-youtube.md` |
| Publish | Upload, check status, attach an upload, or compress/select a thumbnail | `references/publish-youtube.md` |

Do not load unrelated references.

## Resume Router

Inspect project artifacts before acting:

```text
session.json missing                              -> Intake reference
script.md and research.md both missing            -> Ask: research first, or compose from the brief
script.md missing                                 -> compose skill
scenes.json missing                   -> Split reference
image prompts missing                 -> orchestrate-visuals skill
production artifacts incomplete       -> Production reference
final video complete                  -> Done, unless packaging/publishing was requested
YouTube metadata/thumbnails requested -> Package reference
YouTube upload/status requested       -> Publish reference
```

Respect approval gates owned by specialist skills. Do not perform Compose or Orchestrate-Visuals work from this skill.

## Project Contract

Each project lives under `library/<project_name>/`:

```text
session.json -> optional research.md -> script.md -> scenes.json
             -> audio/ + assets/characters/ + images/ + output/final-video.mp4
             -> youtube/metadata.json + thumbnails/ + upload.json
```

The project CLI owns production execution:

```bash
story-video status library/<project_name>
story-video run library/<project_name>
story-video stage voice library/<project_name>
story-video stage illustrate library/<project_name>
story-video stage render library/<project_name>
```

## Hard Rules

- Resume from filesystem artifacts; do not trust `session.json` alone.
- When both research and script are absent, use `ask_question` or a similar user-input tool when available to offer optional research before Compose. Recommend research for externally verifiable claims. Do not persist a routing flag.
- Never bypass specialist approval gates.
- Keep all project outputs inside `library/<project_name>/`.
- Never cast media timings to integers.
- Run production code through `story-video`; run YouTube operations through the standalone `youtube` skill.
- Do not report completion until the owning reference's verification gate passes.
- Once rendering completes and the user approves, commit `library/<project_name>/`; media remains ignored.
