---
name: fetch-memory
description: Fetch relevant memories, insights, decisions, and research from the project's long-term semantic memory. Always delegates to the global /memory skill. Index is `youtube-studio`, namespace is `kahani-ka-chakkar`. Use proactively at the start of any session involving story planning, YouTube research, script writing, or production decisions.
---

# Fetch Memory (`/fetch-memory`)

Retrieves semantically relevant knowledge from the long-term memory for the **kahani-ka-chakkar** YouTube channel project.

- **Index**: `youtube-studio`
- **Namespace**: `kahani-ka-chakkar`

This skill is a thin, project-scoped wrapper. All actual memory operations are delegated to the global `/memory` skill. Do not call `memory.py` or any script directly; invoke `/memory` with the parameters below.

---

## When to Use

Invoke `/fetch-memory` proactively — do not wait for the user to ask:

- **At session start** — whenever picking up any story, script, or YouTube task, fetch relevant context before doing anything else.
- **Before drafting** — before writing a script idea, hook, or scene prompt, fetch prior decisions, rules, and related research.
- **Before making decisions** — before proposing a creative direction, paging strategy, or production rule, check if one already exists.
- **When the user asks** — "what do we know about...", "remind me of...", "did we save anything about...".

---

## Execution Workflow

### Step 1 — Formulate the query

Write a natural-language query that captures what you need. Good queries are specific and contextual:

- ✅ "Hindi YouTube Shorts publish time strategy"
- ✅ "hook rule for first 5 seconds aloo-flood-rescue"
- ✅ "Aloo character voice tone and visual consistency"
- ❌ "stuff" / "notes" / "everything"

### Step 2 — Delegate to `/memory`

Invoke the `/memory` skill with the `fetch` subcommand and these fixed parameters:

```
/memory fetch
  --index        youtube-studio
  --namespace    kahani-ka-chakkar
  --query        "<your natural language query>"
  --top-k        5
  --format       llm_context
```

Use `--top-k 3` for narrow lookups. Use `--top-k 8` when doing a broad session warm-up.

Optionally filter by type when you know what category you need:

```
/memory fetch
  --index        youtube-studio
  --namespace    kahani-ka-chakkar
  --query        "<query>"
  --type         rule
  --top-k        5
  --format       llm_context
```

Do not call `memory.py` or any script directly.

### Step 3 — Integrate the results

- Surface relevant memories to inform the current task — quote titles and key content.
- If nothing relevant is returned, state that clearly and proceed without fabricating context.
- Do not hallucinate memories or assume something was saved if it was not returned.

---

## Common Fetch Patterns

| Task | Suggested query |
|---|---|
| Starting a new story episode | "story ideas kahani-ka-chakkar episode concepts" |
| Writing a scene hook | "hook rules first seconds audience retention hindi" |
| Checking publish timing | "YouTube publish time strategy shorts hindi" |
| Character continuity | "Aloo character design voice tone personality rules" |
| Reviewing past research | "YouTube algorithm research short-form hindi" |
| Platform or production rules | "production rules decisions workflow kahani-ka-chakkar" |

---

## Notes

- Results are ranked by semantic similarity — the most relevant memories come first.
- If the memory store is empty (no index or namespace yet), `/memory` will report that clearly. This is expected in a fresh project.
- The `llm_context` format is designed for direct injection into your working context.
