# Artifact contracts

## Story directory

```text
stories/<story-slug>/
  story.md
  characters.json
  scenes.json
  assets/story_specific/
  videos/
  temp/continuity_frames/
  temp/contact_sheets/
  temp/partial/
  reviews/
  output/final-video.mp4
```

Reusable characters and reusable visual assets remain under the project-level `assets/` directory.

## New-story initialization

Create `characters.json` with an empty `characters` array. Create `scenes.json` with the selected Omni model, aspect ratio, project-relative `characters_file`, and an empty `scenes` array. Do not create dialogue metadata, take folders, or a render manifest.

## `story.md`

Use this minimal structure. The agent must replace placeholders with story-specific content and may omit only fields marked optional.

```markdown
# <Story title>

Status: <current planning or production state>

## Premise and audience

<Core premise, intended audience, and intended experience.>

## Creative contract

- Format:
- Pacing:
- Dialogue:
- Visuals:
- Audio:
- Continuity:

## Story-writing instructions

- Target runtime:
- Clip duration:
- Part construction:
- Clip progression:
- Overload rule:
- Additional persistent story rule: <optional>

## Recurring story elements

- Main characters:
- Locations:
- Objects or motifs:

## Macro structure

| Time | Clips | Major event | Continuity or recurring hook |
|---|---:|---|---|
| <start-end> | <count> | <event> | <hook> |

## Part <number> — <title>

Status: <planning or approval state>
Duration: <seconds and clip count>

### Part brief

- Purpose:
- Entry state:
- Exit state:

### Clip <id> — <start-end> — <title>

- Opening state:
- Visible beats:
- Dialogue: <omit when none>
- Required recurring characters:
- End state:
- Remove first if overloaded: <optional>
```

The agent authors `Story-writing instructions` from the user's direction and approved story decisions when initializing the story. Include only rules that must remain stable across multiple parts; do not place Omni prompt grammar or API behavior there. Present these instructions for approval with the initial story structure.

Before creating or revising any part, reread the current creative contract and story-writing instructions. If the user changes a persistent direction, update this section before continuing; never silently replace or weaken it.

## Character entry

```json
{
  "handle": "@name",
  "name": "Display Name",
  "reference_path": "assets/characters/name.png"
}
```

Register only recurring characters whose appearance must remain consistent across clips.

## Scene entry

```json
{
  "id": "s001",
  "part_id": "part_01",
  "duration_seconds": 10,
  "prompt": "Final authoring prompt with @handles",
  "subjects": ["@name"],
  "reference_images": [],
  "reference_scene_id": null,
  "output_path": "stories/<story-slug>/videos/s001.mp4"
}
```

`first_frame_path` is optional and is used only for an inspected curated continuity frame. All paths are project-relative.

## Review entry

Save one report at `reviews/<scene-id>.json`:

```json
{
  "scene_id": "s001",
  "decision": "needs_fix",
  "attempts": [
    {
      "attempt": 1,
      "kind": "initial",
      "media_valid": true,
      "decision": "needs_fix",
      "findings": ["00:04 character disappears through an unintended snap"],
      "diagnosis": "model continuity failure during the camera move",
      "repair_applied": null
    }
  ],
  "next_action": "retry"
}
```

Allowed decisions are `accepted`, `accepted_with_note`, `fix_next_scene`, and `needs_fix`.

Append one entry after every reviewed generation; never overwrite earlier attempts. `kind` is `initial` for attempt 1 and `repair` for retries. `repair_applied` records the concrete change that produced a retry and is `null` for the initial generation. The top-level `decision` and `next_action` reflect the latest attempt.

A scene may contain at most four attempts without fresh user authorization: one initial generation and three repair retries. If attempt 4 remains `needs_fix`, set `next_action` to `await_user`.
