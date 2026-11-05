# Artifact contracts

## Production root

```text
<studio-root>/
  characters.json          ← global character registry (source of truth for identity)
  assets/characters/       ← character reference images
  projects/.../<production-root>/
    story.md
    characters.json        ← production-specific characters only; empty array when all are global
    locations.json
    scenes.json
    assets/
    videos/
    temp/continuity_frames/
    temp/contact_sheets/
    reviews/
    output/final-video.mp4
```

The production root is the directory that owns the target `story.md` and `scenes.json`. It may be nested to support collections, brands, series, or other organizational groupings. Reusable characters and reusable visual assets remain under the studio-level `assets/` directory. Existing production directories under `stories/` remain valid and are not relocated.

For a new production root, create the canonical files and directories above directly from this contract.

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

### Two-tier character registry

Character identity is split across two files:

**Studio registry** (`characters.json` at studio root) — source of truth for all reusable characters. Contains the full entry:

```json
{
  "handle": "@name",
  "name": "Display Name",
  "reference_path": "assets/characters/name.png",
  "profile": "Concise, stable model-facing identity and performance grounding",
  "description": "Concise narrative role, relationships, and motivation"
}
```

Follow [character-readiness.md](character-readiness.md) when authoring or validating these fields.

**Production registry** (`<production-root>/characters.json`) — production-specific characters only. Uses the same full schema. For productions where all characters are global, this file holds an empty array:

```json
{
  "characters": []
}
```

Project-level entries for script compatibility (when a studio character's `reference_path` must be confirmed for a specific project) may contain only `handle`, `name`, and `reference_path`.

**Resolution rule:** for any `@handle`, check the project registry first, then fall back to the studio registry. If an entry exists in both, the project entry wins.

Register only recurring characters whose appearance must remain consistent across clips. Describe one-off or incidental figures directly in the scene prompt.

## Location entry

Recurring locations use the same project/studio ownership pattern as characters, but every location handle must begin with `@location-`.

```json
{
  "handle": "@location-water-point",
  "name": "Bhairampur Public Water Point",
  "reference_path": "<production-root>/assets/locations/water-point.jpg",
  "profile": "Concise stable spatial/architectural grounding",
  "description": "Optional narrative function of the place"
}
```

Production locations live in `<production-root>/locations.json` under a `locations` array. A studio-root `locations.json` may hold reusable places. Production entries override studio entries with the same handle.

Register only places whose visual identity must persist across clips. A location profile should contain stable geography, layout, architecture, materials, or orientation cues that the reference image alone may not reliably communicate. Do not put temporary weather, temporary props, current characters, or scene-specific action in the profile.

## Scene entry

```json
{
  "id": "s001",
  "part_id": "part_01",
  "prompt": "Final authoring prompt with character, @location-*, and optional @narration-* handles",
  "subjects": ["@name"],
  "locations": ["@location-water-point"],
  "reference_images": [],
  "reference_scene_id": null,
  "output_path": "<production-root>/videos/s001.mp4"
}
```

Resolution rules:

- recurring character handles are visual references resolved from character registries and must be listed in `subjects`;
- `@location-*` handles are visual references resolved from location registries and must be listed in `locations`;
- `@narration-*` handles resolve from `voices.json`, remain audio-only, and belong in neither `subjects` nor `locations`;
- a declared character or location must appear in the authored prompt, and a recurring character/location handle in the prompt must be declared in the matching array;
- `reference_images` are for supplemental scene-specific visual evidence, not a substitute for recurring character or location registration.

`first_frame_path` is optional and is used only for an inspected curated continuity frame. All persisted paths are repository-relative.

## Review entry

Save one report at `reviews/<scene-id>.json`:

```json
{
  "scene_id": "s001",
  "decision": "needs_fix",
  "video_path": "<production-root>/videos/s001.mp4",
  "video_sha256": "<written by the runner>",
  "contact_sheet_path": "<production-root>/temp/contact_sheets/s001.png",
  "media_valid": true,
  "findings": ["00:04 character disappears through an unintended snap"],
  "diagnosis": "model continuity failure during the camera move",
  "repair_applied": null,
  "history": [],
  "next_action": "retry"
}
```

Decisions are `pending_review`, `accepted`, `accepted_with_note`, `fix_next_scene`, and `needs_fix`. The runner creates the review slot and owns `video_path`, `video_sha256`, and `history`; the reviewer fills the observable evidence, diagnosis, decision, and next action for the active video. When a rejected video is replaced, the runner archives its video, contact sheet, and review fields before opening a fresh review slot.

Dependent-scene generation and final rendering verify that the active video matches `video_sha256` and has an accepted decision.
