---
name: create-prompt
description: Create and save one self-contained execution prompt from a loosely specified request. Use when the user wants a reusable prompt file for an ad-hoc task or behavior, rather than changing the project's permanent workflow.
---

# Create Prompt

Create exactly one prompt artifact. Do not execute the prompt or perform the task it describes unless the user separately asks for that work.

## Clarify

Before writing, use `ask_question` to resolve only the missing details that materially affect the prompt:

- the objective and intended outcome
- who or what will execute the prompt
- relevant inputs, files, or context
- required behavior and decision points
- constraints, authorization boundaries, and completion evidence

Do not ask the user to repeat information already provided. Group related questions and keep them concise. If `ask_question` is unavailable, ask the same necessary questions directly in chat.

## Write

Turn the confirmed requirements into a standalone execution prompt. Include only instructions needed to perform the requested task reliably. Make the expected output and completion condition explicit.

Do not introduce project-wide rules, speculative capabilities, or unrelated workflow steps. A prompt may invoke an existing skill when the requested task requires it, but it must not duplicate that skill's internal instructions.

## Save

Save the prompt as a Markdown file under `<current-working-directory>/prompts/` unless the user specifies another destination. Derive a short kebab-case filename from the objective when no filename is provided.

Create the destination directory if needed. Never overwrite an existing prompt without the user's approval; ask whether to replace it or choose a new filename.

After saving, report the file path and a one-sentence summary of what the prompt instructs.
