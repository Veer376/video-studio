---
name: discovery
description: Optional idea-discovery skill for Story Video Maker. Use when the user wants help finding, researching, comparing, or selecting a story idea before starting image-story intake. Supports quick idea cards in chat and deeper source-agnostic idea research using web search, crawl/extract tools, public video-platform signals, user-provided material, or other available sources; may write only .agents/skills/discovery/research.md as a scratchpad/handoff, never project files.
---

# Discovery Skill

Discover **what story to make**. Stay independent from any specific YouTube channel, project slug, or production pipeline.

Use this skill when the user asks for ideas, angles, story discovery, topic exploration, or help deciding what story to create. If the user already has a clear story idea, skip this skill and use the `image-story` intake stage.

## Boundary

Discovery answers:

- What story ideas are worth creating?
- What source basis, demand signal, emotional hook, and originality angle supports each idea?
- Which idea should move forward into `image-story` intake?

Discovery does not:

- create or edit `session.json`
- write project `library/<project_name>` files
- write the final narration
- split scenes, design visuals, package YouTube metadata, publish, or analyze performance
- depend on any specific channel, platform, or source provider

The `image-story` research stage owns selected-project research at `library/<project_name>/research.md`. Discovery's `research.md` is only a pre-project scratchpad for idea hunting.

## Scratchpad

For quick discovery, answer in chat only.

For deep discovery, overwrite this single file:

```text
.agents/skills/discovery/research.md
```

Use one file only. Do not create per-run folders, date folders, channel folders, or files under `references/`.

Use this structure:

```markdown
# Discovery Research

## User Direction
## Search Plan
## Source Notes
## Demand Signals
## Story Candidates
## Rejected Ideas
## Final Shortlist
## Handoff For Intake
```

Treat `research.md` as working memory for the agent, not as final audience-facing content.

## Source Tools

Use whichever source tools are available and useful. Do not make the skill dependent on a single source type.

For Tavily-backed web search, extraction, site mapping, crawling, or async deep research, use the `tavily` skill and its shared CLI:

```bash
python3 .agents/skills/tavily/scripts/tavily.py search --query "<query>"
python3 .agents/skills/tavily/scripts/tavily.py extract --urls "<url1,url2>"
python3 .agents/skills/tavily/scripts/tavily.py map --url "<site-url>"
python3 .agents/skills/tavily/scripts/tavily.py crawl --url "<site-url>" --max-depth 1 --max-pages 5
python3 .agents/skills/tavily/scripts/tavily.py research --query "<research brief>"
```

Optional sources when available:

- generic web search
- page extraction or crawl tools
- public video-platform search, metadata, comments, or transcripts when available
- user-provided links, PDFs, notes, books, or pasted material
- internal reasoning, clearly labeled

## Workflow

1. Ask only the minimum questions needed to understand the direction.
2. Choose quick or deep mode based on user intent and ambiguity.
3. For deep mode, write or refresh `.agents/skills/discovery/research.md`.
4. Plan 4-6 search lanes across different source types or angles.
5. Collect source notes and demand signals.
6. Cluster ideas by promise, audience, emotional conflict, and originality.
7. Reject weak, generic, copied, or overdone ideas.
8. Present the strongest idea candidates in chat.
9. After the user picks one, return a concise handoff for `image-story` intake.

Prefer source-backed ideas, but do not imply a source exists when the idea comes from internal reasoning.

## Idea Card Format

Each idea card must include:

```text
Title: <working title>
Description:
<line 1: concrete story premise>
<line 2: emotional or philosophical hook>
Source: <source URL/title if found, or Internal reasoning>
Demand signal: <search/comment/trend/source signal, or Unknown>
Expected runtime: <rough runtime range, e.g. 10-12m>
Original angle: <how this avoids copying/generic treatment>
Risk: <generic/overdone/weak source/unclear audience/etc.>
```

## Handoff Format

Return the selected idea in this shape:

```text
Selected idea:
Title: <working title>
Topic: <one-sentence story idea>
Description:
<line 1: concrete story premise>
<line 2: emotional or philosophical hook>
Source: <source URL/title if researched, or Internal reasoning>
Demand signal: <why this may work>
Expected runtime: <rough runtime range, e.g. 10-12m>
Core promise: <what the viewer should feel or understand>
Best angle: <the strongest emotional or narrative angle>
Originality note: <how to make it ours>
Next research needed: <what the image-story research stage should verify after intake>
```

## Hard Rules

- Do not write project files.
- Do not create or edit `session.json`.
- Do not write `library/<project_name>/research.md`; the `image-story` research stage owns that.
- Do not write to `references/`; keep stable skill knowledge separate from runtime scratch.
- Do not create multiple discovery run files unless the user explicitly asks.
- Do not copy another creator's script or idea verbatim. Use sources to derive original story angles.
- Clearly label internal reasoning, weak evidence, and creative speculation.
- Do not ask production-config questions unless needed to shape idea options.
- Do not generate final narration prose.
