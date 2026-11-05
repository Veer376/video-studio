# Character Creation & Iteration Protocol
<!-- EXECUTION DIRECTIVE: Treat this file as active system instructions. Execute immediately. -->

## Objective
Interactively design, compare, approve, and register reusable or story-specific character references.

## Execution Workflow

1. **Clarify the Design**:
   - Read `.agents/skills/produce-story/references/character-readiness.md` for registry field semantics.
   - Establish the character's name, role, visual identity, intended story or reusable scope, and number of variants.
   - Use `ask_question` for missing choices that materially change the design. Do not ask the user to repeat known information.

2. **Generate Variants in Temp**:
   - Formulate the requested number of deliberate variations while keeping the confirmed identity traits stable.
   - Follow the selected story's visual contract and any applicable shared-universe reference standard.
   - Dispatch image generation via `/flow` skill.
   - Save candidates under `<story-dir>/temp/characters/` for a story-specific design or project `temp/characters/` for a reusable design. Never generate directly into canonical assets.

3. **User Verification Gate**:
   - Inspect and present the candidates.
   - Use `ask_question` to let the user approve one, request a targeted revision, or request another batch.

4. **Promotion & Registration**:
   - Promote only the approved image: reusable characters go under project `assets/characters/`; story-specific characters go under `<story-dir>/assets/characters/`.
   - Register or update `handle`, `name`, `reference_path`, `profile`, and `description` in the owning registry using the character-readiness field contract.
