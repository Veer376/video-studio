---
name: targeted-skill-editor
description: Make minimal, semantics-first updates to Codex skills when a skill produced wrong, diluted, overbroad, or low-quality behavior. Use for editing SKILL.md instructions, tightening trigger semantics, replacing misleading terms, adding concrete guardrails, and improving a skill recursively without rewriting it wholesale.
---

# Targeted Skill Editor

Use this skill to improve another skill after a real failure, confusing behavior, or user correction. Treat the observed failure as evidence that some wording, structure, or missing guardrail shaped the agent toward the wrong action.

## Core Principle

Semantics are the interface. A small phrase like `Base image`, `Overlay text`, `may create`, or `consider examples` can steer future agents more strongly than a long explanation. Prefer changing the few words that caused the wrong behavior over adding broad new sections.

User corrections are evidence. When the user explains why wording produced a bad result, preserve the distinction between the user's goal and the exact proposed wording. Improve the skill so a future agent reaches the intended behavior from the instructions alone.

## Workflow

1. Read the full target `SKILL.md` before editing.
2. Identify the failure mode in concrete terms: what the agent did, what the user expected, and which instruction wording likely caused the gap.
3. Locate the smallest causative section first. Clean or rename the existing semantics before adding new instruction blocks.
4. Classify the fix:
   - **Rename misleading semantics:** replace terms that imply the wrong workflow.
   - **Tighten a weak rule:** convert soft guidance into an explicit default, prohibition, or quality gate.
   - **Remove dilution:** shorten instructions that distract from the important behavior.
   - **Add a missing guardrail:** add the smallest rule that prevents repeat failure.
5. Make the smallest coherent edit. Avoid rewriting the whole skill unless the structure itself is the failure.
6. Search the edited skill for old terms, contradictory rules, duplicate numbering, and stale schema fields.
7. Validate with a focused diff and summarize only the behavior change.

## Editing Rules

- Preserve the skill's original purpose, boundaries, and file layout unless they are directly causing the problem.
- Prefer targeted substitutions over new paragraphs.
- Use strong words only where agent compliance must be non-negotiable: `must`, `never`, `hard default`, `stop`, `do not`.
- Do not add arbitrary limits to make work easier. If the user asks to reduce dominance or verbosity, compress wording without restricting useful agent judgment.
- When quality matters, add a concrete quality gate instead of vague advice. Example: `Do not use low-view videos as market references; keep searching for 100k+ relevant examples.`
- When output quality depends on creative judgment, specify what makes an output click-worthy, useful, or invalid.
- When a user adds a weak but correct rule, strengthen it into an operational instruction with clear pass/fail behavior.
- Do not hide weak fallback behavior inside permissive wording. If fallback is allowed, name the trigger and require explicit user approval when quality or truthfulness would degrade.
- If the user is still discussing the change, discuss only. Do not edit until they ask to apply it.

## Semantic Patterns

Try to focus on the semantics like `In-image text` when text must be generated as part of an image and `Overlay text` unless the workflow actually allows a separate local overlay. etc. Try to make it more concise and to the point.
