# Video Studio control plane

Status: architecture hypothesis; no runtime behavior has been changed.

Date: 2026-08-28

## Reason

Canonical production state is currently managed through a mixture of direct file edits and separate scripts. The agent must repeatedly identify story paths, configuration files, output paths, and review records. This increases the chance of editing the wrong artifact or bypassing a lifecycle rule.

The proposed change is a generalization improvement: establish one agent-facing control plane while preserving the existing tested generation, review, and rendering implementations underneath it.

## Vocabulary

- **Studio**: this repository, including shared assets, skills, engines, applications, and all story projects.
- **Project**: one production directory currently stored at `stories/<slug>/`.
- **Scene**: one generated-video unit registered in the current project's `scenes.json`.
- **Current project**: runtime context selected once for a working session. It is not story content and must not be stored in `story.md` or `scenes.json`.

The repository and its existing directories do not need to be renamed to adopt these semantics.

## Target outcome

The agent uses one `video-studio` command surface for project selection, project creation, canonical artifact changes, scene generation, review, repair, and rendering. Operational commands act on the current project and do not repeat a project name or configuration path.

Low-level scripts remain reusable implementation engines. They are not removed during migration.

## Non-goals for the control-plane migration

- Do not change Gemini prompt semantics.
- Do not introduce contract and craft review gates.
- Do not redesign contact-sheet sampling.
- Do not migrate or normalize existing project files.
- Do not remove legacy-review compatibility.
- Do not fold the Render Studio timeline editor into the production state machine.
- Do not enforce new progression policy until the wrapper commands have parity with current behavior.

## Current repository findings

- Ten project directories currently contain 203 registered scenes.
- Every project has `story.md`, `characters.json`, and `scenes.json`.
- The core scene schema is shared, while optional fields such as `duration`, `title`, and `first_frame_path` vary by project.
- `story.md`, `characters.json`, `scenes.json`, and reviewer-owned review fields are directly edited today.
- `generate_scenes.py` owns active-video generation, rejected-video archiving, restore, hashes, and review-slot creation.
- `review_contract.py` owns review validation and atomic review writes, but has no reviewer submission API.
- `render_video.py` validates accepted active clips and their hash bindings before rendering.
- Several scripts still contain story-specific default configuration paths.
- `app/vp.py` is a separate partial command surface and currently does not match every maintained backend argument contract.
- Render Studio is a repository-wide post-production browser/editor, not a project lifecycle controller.
- The current test suite has 39 passing tests. It does not cover project creation, current-project resolution, canonical story/scene writers, or a unified CLI.

## Current-project resolution hypothesis

Operational commands should not accept `--project` repeatedly. Resolve the current project in this order:

1. `VIDEO_STUDIO_PROJECT`, when supplied by an agent host or isolated session.
2. The current working directory, when it is inside `stories/<slug>/`.
3. A workspace-local selection created by `video-studio project use <slug>`.
4. Otherwise stop with a structured `project_context_missing` error.

Never guess a default project. Every response from `video-studio context` should report the selected slug, absolute project directory, and resolution source (`environment`, `cwd`, or `workspace_selection`).

The environment and working-directory precedence prevents a shared workspace selection from overriding an isolated task. Before implementing workspace selection, test concurrent-task behavior explicitly.

## Proposed command surface

### Context and project lifecycle

```text
video-studio context
video-studio project list
video-studio project create --title TITLE --aspect-ratio 9:16 [--slug SLUG] [--clip-duration 10]
video-studio project use SLUG
video-studio project status
```

`project create` is the one operation that necessarily receives project identity. It should derive the slug when omitted, create the canonical directory structure and minimal files atomically, validate them, and select the new project only after successful creation.

Operational commands after selection do not receive a project name.

### Story and character state

```text
video-studio story show
video-studio story replace --input -
video-studio story validate

video-studio character list
video-studio character add --input -
video-studio character update HANDLE --input -
```

Large model-authored content should enter through standard input or a structured input document. The CLI, not the agent, writes the canonical file. Destructive character removal is deferred until reference checks and recovery behavior are defined.

### Scene state and generation

```text
video-studio scene list
video-studio scene show SCENE_ID
video-studio scene add --input -
video-studio scene update SCENE_ID --input -
video-studio scene generate [SCENE_ID]
video-studio scene restore SCENE_ID a1
```

Scene add/update should accept one complete scene contract, validate IDs, handles, references, paths, and ordering, and write `scenes.json` atomically. `scene generate` should initially delegate to the existing generator without changing its lifecycle.

When `SCENE_ID` is omitted, a future policy layer may select the next eligible scene. That behavior must not be introduced until eligibility is defined and tested.

### Review

```text
video-studio review status [SCENE_ID]
video-studio review submit SCENE_ID \
  --decision needs_fix \
  --finding "00:04 character disappears" \
  --diagnosis "temporal continuity failure"
```

The deferred standalone `scripts/review.py` hypothesis moves under the unified command surface. The model supplies only judgment:

- `--decision`: `accepted`, `accepted_with_note`, `fix_next_scene`, or `needs_fix`;
- repeatable `--finding` values;
- `--diagnosis` when a failure needs repair;
- optional `--repair-applied` when reviewing a replacement.

The command resolves video, review, and contact-sheet paths; verifies the video hash and media; derives `media_valid` and `next_action`; preserves runner-owned state; and writes atomically. It must read legacy reviews but not rewrite them.

### Render

```text
video-studio render [--dry-run]
```

The command resolves the current project's configuration and canonical final output, then delegates to the existing renderer. Post-production utilities such as cutting, watermarking, music mixing, looping, and the Render Studio UI remain separate until a concrete lifecycle need justifies integrating them.

## Structured interface rules

- Standard output is structured JSON for agent consumption.
- Errors are structured and use non-zero exit codes.
- Paths returned to the agent may be absolute for tool use, but persisted canonical paths remain project-relative.
- Short scalar judgments use CLI flags; large Markdown or JSON content uses standard input.
- Commands are non-interactive.
- Mutating commands validate first and write atomically.
- Repeating an identical completed mutation is a successful no-op where safe.
- A conflicting repeated mutation stops rather than silently overwriting state.

## Ownership

| Concern | Owner |
|---|---|
| Story, scene, and review judgment | Model using domain skills |
| Current-project resolution | Video Studio control plane |
| Canonical file validation and persistence | Video Studio control plane |
| Prompt compilation | Existing prompt skill and compiler |
| Generation, archive, restore, active-video hashes | Existing generation engine |
| Visual and audio inspection | Model using actual inspection capabilities |
| Review path and state mechanics | Review contract library through the control plane |
| Final eligibility and concatenation | Existing renderer |
| Story-specific progression policy | Future project configuration |

The CLI cannot prove that the model inspected an image or listened to audio. Skills own that requirement; the control plane can only prove that bound evidence exists.

## Migration plan

### Phase 0 — Characterize

- Preserve the 39-test baseline.
- Add tests for project discovery and schema variants without changing production behavior.
- Record active and legacy review compatibility fixtures.

### Phase 1 — Read-only control plane

- Introduce the `video-studio` executable and internal package.
- Implement `context`, `project list`, `project status`, `scene list/show`, and `review status`.
- Do not write production state.

### Phase 2 — Project context and initialization

- Implement `project use` and isolated context precedence.
- Implement atomic `project create` using the existing artifact contract.
- Do not migrate existing projects.

### Phase 3 — Existing engine wrappers

- Implement `scene generate`, `scene restore`, and `render` as thin calls into maintained Python functions.
- Remove story-specific defaults from the agent-facing path, but keep low-level scripts compatible.
- Verify output and exit-code parity.

### Phase 4 — Canonical state writers

- Implement review submission first because an atomic review writer already exists.
- Add scene add/update with full schema validation.
- Add story and character writers after their validation contracts are explicit.
- Update skills to use commands only after each writer has parity tests.

### Phase 5 — Policy enforcement

- Define one eligibility function for sequential scene progression.
- Move configurable progression rules into project configuration.
- Only then prevent direct canonical mutation in agent instructions.

### Phase 6 — Production improvements

- Contact-sheet evidence commands and manifests.
- Contract-versus-craft review assessments.
- Film-level directing contract refinements.
- Audio verification and transcript alignment.

Each phase must be independently releasable and must not require the following phase to preserve existing production behavior.

## Validation scenarios

The control plane must work without story-type assumptions across at least:

1. a long-form, 16:9, dialogue-heavy drama with many scenes;
2. a short, 9:16, action-led cartoon with literal frame continuity;
3. a short vertical advertisement that mixes generated performance and real interface plates.

Legacy reviews must remain renderable, active reviews must retain hash binding, and existing direct engine tests must continue to pass.

## Decisions intentionally deferred

- Whether workspace selection is stored under `.video-studio/` or supplied entirely by the host integration.
- Whether the installed command is named `video-studio` or receives a shorter alias.
- The exact structured input schema for replacing `story.md`.
- Whether scene eligibility is automatic or always requires an explicit scene ID.
- The schema and progression effect of contract and craft assessments.
- Contact-sheet modes, dialogue overlays, and evidence-manifest schema.

These are decision checkpoints, not missing implementation details. They should be resolved with tests or concrete workflow evidence before the owning phase begins.
