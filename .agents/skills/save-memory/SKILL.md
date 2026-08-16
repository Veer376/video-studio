---
name: save-memory
description: Save a high-value insight, research finding, creative decision, YouTube strategy, or production rule into the project's long-term semantic memory. Always delegates to the global /memory skill. Index is `youtube-studio`, namespace is `kahani-ka-chakkar`. ONLY invoke when the user explicitly asks, or the agent proposes and the user confirms. Never save autonomously without explicit user approval.
---

# Save Memory (`/save-memory`)

Saves knowledge into the long-term semantic memory for the **kahani-ka-chakkar** YouTube channel project.

- **Index**: `youtube-studio`
- **Namespace**: `kahani-ka-chakkar`

This skill is a thin, project-scoped wrapper. All actual memory operations are delegated to the global `/memory` skill. Do not call `memory.py` directly; invoke `/memory` with the parameters below.

---

## Trigger Rules

This skill ONLY fires in two cases:

1. **User explicitly asks** — the user says "save this", "remember this", "store this", or invokes `/save-memory`.
2. **Agent proposes + user confirms** — the agent may surface something worth saving, but MUST present a preview and wait for the user to say yes before proceeding.

Never save silently. Always show a confirmation preview first.

---

## Memory Types

| Type | Use for |
|---|---|
| `insight` | Audience behaviour, algorithm observations, platform trends |
| `rule` | Hard production or creative rules that must hold consistently |
| `strategy` | Multi-step plans, campaign ideas, content strategies |
| `script-idea` | Story briefs, hook concepts, episode outlines, dialogue fragments |
| `research` | External findings, competitor analysis, industry trends |
| `analytics` | Interpreted conclusions from channel data — growth patterns, retention trends, what worked (see granularity rule below) |
| `decision` | Finalized creative or technical decisions (palette, pacing, format) |
| `character` | Character notes, voice tone, visual consistency rules |
| `workflow` | Process improvements, pipeline rules, tool usage patterns |

---

## Execution Workflow

### Step 1 — Extract the content

Identify a clear, self-contained summary of what the user wants saved. It must be useful when retrieved in a future session with no prior context.

**Granularity filter — apply before every save:**
Ask: *"Would this still be useful in 3 months?"* If the value is tied to a specific date, a single video's raw number, or a one-off observation that won't repeat, do not save it.

- ✅ Save: *"Shorts with dramatic Hindi questions in titles outperform descriptive titles by ~40% CTR on this channel"*
- ❌ Skip: *"CTR was 4.2% on Aug 12 with 1,847 impressions"* — too granular, too time-bound
- ✅ Save: *"Retention drops sharply after 7s when there is no dialogue — silence kills watch time on this format"*
- ❌ Skip: *"Scene s003 had 62% average view duration"* — belongs in a review file, not memory

If the user asks to save something that fails this filter, gently flag it and suggest either a more durable phrasing or skipping the save entirely.

### Step 2 — Determine metadata

- **title**: Short, specific headline (≤ 80 chars). Avoid vague titles like "YouTube Note".
- **type**: One from the table above.
- **tags**: Comma-separated, lowercase. Include the story slug or topic where relevant (e.g. `hook,hindi,retention`, `aloo-flood-rescue,script-idea`).
- **source** *(optional)*: Conversation ID, URL, or "user-stated".

### Step 3 — Show a confirmation preview

Always prompt the user for confirmation before committing anything to memory.

1. **If the `ask_question` tool is available in your toolset:**
   Use `ask_question` to render an interactive confirmation modal with selectable options.
2. **If `ask_question` is not available:**
   Present the markdown preview and ask directly in chat text:

```
📝 About to save to memory:
  Index:     youtube-studio
  Namespace: kahani-ka-chakkar
  Title:     <title>
  Type:      <type>
  Tags:      <tags>
  Preview:   <first 200 chars>...

Confirm? (yes / no)
```

Do NOT skip this confirmation step, even if the user just typed "save this".

### Step 4 — Delegate to `/memory`

Invoke the `/memory` skill with the `save` subcommand and these fixed parameters:

```
/memory save
  --index        youtube-studio
  --namespace    kahani-ka-chakkar
  --title        "<title>"
  --type         <type>
  --tags         "<tags>"
  --source       "<source>"
  --text         "<full content>"
```

Do not call `memory.py` or any script directly.

### Step 5 — Report success

After `/memory` confirms, report:
- The record ID (e.g. `mem_20260816_171800_abc123`)
- Title and type saved
- One-line confirmation

---

## What NOT to save

- **Raw metrics** — individual video stats, impression counts, specific date-stamped numbers
- **Time-bound snapshots** — anything whose value expires within weeks (e.g. "trending audio this week")
- Raw video paths, image paths, or binary references
- Transient debug output or one-off error traces
- Generation prompts already stored in `scenes.json`
- Anything the user has not explicitly approved

When in doubt, ask: *"Would an insight derived from this be more useful than the raw data?"* If yes, save the insight instead.
