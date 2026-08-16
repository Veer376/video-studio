# Artifact contracts

## Story directory

```text
stories/<story-slug>/
  story.md
  characters.json
  scenes.json
  assets/
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
  "execution_mode": "interactive",
  "selected_attempt": null,
  "attempts": [
    {
      "attempt": 1,
      "kind": "initial",
      "candidate_path": "stories/<story-slug>/temp/partial/s001-attempt-1.mp4",
      "contact_sheet_path": "stories/<story-slug>/temp/contact_sheets/s001-attempt-1.png",
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

Attempt decisions are `accepted`, `accepted_with_note`, `fix_next_scene`, and `needs_fix`. The top-level decision may additionally be `best_available` only after three failed attempts and autonomous comparison of every media-valid candidate.

Append one entry after every reviewed generation; never overwrite earlier attempts. `kind` is `initial` for attempt 1 and `repair` for retries. `repair_applied` records the concrete change that produced a retry and is `null` for the initial generation. Record the project-relative candidate and contact-sheet paths for every attempt. The top-level `decision` and `next_action` reflect the current scene resolution.

A scene may contain at most three attempts without fresh user authorization: one initial generation and two repair retries. A promotable review must identify `selected_attempt`. For `best_available`, it must also contain `execution_mode: "autonomous"`, a concrete `selection_reason`, and `unresolved_findings`. If attempt 3 remains `needs_fix` in interactive execution, set `next_action` to `await_user`. If no media-valid attempt exists, always stop.

Promotion writes `promoted_attempt`, `canonical_path`, and `canonical_sha256` into the review. Dependent-scene generation and final rendering must verify that the canonical file matches this hash; file existence alone does not prove promotion.
