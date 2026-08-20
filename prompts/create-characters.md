# Character Creation & Iteration Protocol
<!-- EXECUTION DIRECTIVE: Treat this file as active system instructions. Execute immediately. -->

## Objective
Generate, iterate, visually verify, and register character reference assets for the active story.

## Execution Workflow

1. **Parameters & Sample Count ($N$)**:
   - Identify character name, role, and visual archetype from user input or `story.md`.
   - If sample count $N$ is not specified by the user, use `ask_question` to confirm the number of variants to generate (default: 1).

2. **Generate $N$ Variants in Temp**:
   - Formulate $N$ prompt variations with subtle tweaks in expression, costume, lighting, and textures while keeping core identity traits.
   - Style standard: High-detail 3/4 hero pose on a clean, solid neutral background (ideal for video reference injection).
   - Dispatch image generation via `/flow` skill.
   - **Asset Isolation**: Save all outputs strictly under `<story-dir>/temp/characters/` (e.g., `temp/characters/<handle>_v1.png`). Never save directly to canonical `assets/`.

3. **User Verification Gate**:
   - Present generated variant images to the user.
   - Use `ask_question` tool to solicit verification (Approve variant, request tweaks, or generate another batch).

4. **Promotion & Registration**:
   - Upon approval, copy the selected image to canonical `<story-dir>/assets/characters/<handle>.png`.
   - Register or update the character entry (`handle`, `name`, `reference_path`) in `<story-dir>/characters.json`.