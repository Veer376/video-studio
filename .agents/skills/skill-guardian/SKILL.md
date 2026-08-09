---
name: skill-guardian
description: Guards the semantic integrity of image-story-studio skills. Use before making any change to a skill in this project. Blocks changes that add project-specific content, break generalization, or lack a concrete reason.
---

# Skill Guardian

Skills in this project are hard to build and easy to corrupt. A single wrong line cascades into a maintenance loop. This skill stops that before it starts.

Invoke this before editing any `.agents/skills/` file in this project.

---

## Step 1 — Require a Concrete Reason

Before any edit, the agent must state the exact reason:

> *"The change is needed because: [specific broken behavior / wrong output / incorrect logic]."*

If the reason is vague ("improve it", "make it cleaner", "add more detail") — **stop. Do not proceed.** Ask the user to be specific.

---

## Step 2 — Classify the Change

Classify the proposed edit into exactly one of these:

| Class | Description | Allowed? |
|---|---|---|
| **Script bug** | A script produces wrong output (wrong file, wrong field, crash) | ✅ Always |
| **Semantic error** | The skill instruction produces incorrect agent behavior (wrong logic, stale reference, contradicts another step) | ✅ Always |
| **Generalization improvement** | Removes a hardcoded assumption, makes the skill work for more story types | ✅ If it passes Step 3 |
| **Specificity addition** | Adds project-specific content, hardcodes a style/value, narrows the skill's scope | ❌ Block it |
| **Scope creep** | Adds responsibility the skill doesn't own (render style, story concept, intake data) | ❌ Block it |

If the change is Class 4 or 5, redirect: the content belongs in `session.json`, `intake`, or user input — not in the skill.

---

## Step 3 — Generalization Test (for Class 3 only)

Ask: *"Does this rule hold true for every story this skill could ever process?"*

Test it against these three story types mentally:
1. A non-human fable (seed, river, animal protagonist)
2. A biographical/devotional story (Osho, Vivekananda, Gandhi)
3. A mythological narrative (Ramayana, Mahabharata)

If the rule fails for even one — it is **not generalizable**. It is dynamic content that belongs in `session.json` or as a user question at runtime. Tell the user clearly.

---

## Step 4 — Ownership Check

Every piece of content has an owner. Before adding anything, verify it doesn't already belong to another skill:

| Content Type | Owner |
|---|---|
| Render style / visual quality (3D, 2D, cinematic) | `intake` → `session.json visual.style` |
| Story idea, tone, audience | `intake` → `session.json brief` |
| Script text, scenes split | `split-script` |
| Character anthropomorphization, prompt craft, framing | `orchestrate-visuals` |
| Voice, TTS language | `voice` skill |

If the proposed addition belongs to another owner — reject and redirect.

---

## Hard Rules

1. **One reason, one change.** A single edit must trace to a single concrete reason. Multi-reason edits must be broken apart and evaluated separately.
2. **No "while we're here" edits.** Do not fix adjacent issues in the same edit unless they share the exact same root cause.
3. **Semantic changes must move toward generalization, never away from it.** If the edit makes the skill narrower or more project-specific, it is wrong by definition.
4. **Fewer words is better.** A skill that is shorter and does less is more durable than one that is longer and does more. Prefer removing content over adding it.
