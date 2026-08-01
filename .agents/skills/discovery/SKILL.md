---
name: discovery
description: Optional idea-discovery skill for Story Video Maker. Use when the user wants help finding, researching, comparing, or selecting an image-story idea before intake. Does not write project files; returns a concise handoff brief that intake can use.
---

# Discovery Skill

This is a standalone optional helper for image-story projects. Its job is to discover and choose **what story to make**. It does not configure production, write files, write the final script, split scenes, design visuals, or run the pipeline.

Use this skill when the user asks for ideas, angles, story discovery, topic exploration, or help deciding what story to create.

If the user already has a clear story idea, skip this skill and use `intake`.

## Boundaries

Discovery answers:

- What story should we create?
- Why is this story worth making?
- What is the title, source basis, expected runtime, core promise, and emotional angle?

Intake answers:

- Duration, format, language, voice, visual style, and pipeline config.

Research answers:

- Source-backed material for the selected brief and writes `research.md`.

## Tools

This skill bundles the same Tavily CLI tools as `research`:

```bash
python3 .agents/skills/discovery/scripts/tavily_search.py --query "<query>"
python3 .agents/skills/discovery/scripts/tavily_extract.py --urls "<url1,url2>"
python3 .agents/skills/discovery/scripts/tavily_crawl.py --url "<url>" --mode map
python3 .agents/skills/discovery/scripts/tavily_research.py --query "<query>"
```

They load `TAVILY_API_KEY` from `~/.config/projects/.env`.

If another research skill or external research tool is attached, you may use it for idea discovery. Keep this skill's output contract unchanged.

## Workflow

1. Ask only the minimum questions needed to understand the desired direction. Prefer generating options over long interviews.
2. Research lightly if useful: find story-worthy angles, real incidents, spiritual/philosophical hooks, or surprising contrasts.
3. Present 3 strong idea candidates as compact idea cards.
4. After the user picks one, return a short handoff brief in chat for `intake`.

Each idea card must include:

```text
Title: <working title>
Description:
<line 1: concrete story premise>
<line 2: emotional or philosophical hook>
Source: <source URL/title if found through research, or "Internal reasoning" if inferred>
Expected runtime: <rough timestamp/runtime range, e.g. 00:00-00:45 or 45-60s>
```

If the source is from the internet, include the strongest source URL or source title. If it is an invented or internally reasoned angle, say that clearly instead of implying a real source.

## Output

Do not create or edit files.

Return the selected idea in this shape:

```text
Selected idea:
Title: <working title>
Topic: <one-sentence story idea>
Description:
<line 1: concrete story premise>
<line 2: emotional or philosophical hook>
Source: <source URL/title if researched, or Internal reasoning>
Expected runtime: <rough timestamp/runtime range>
Core promise: <what the viewer should feel or understand>
Best angle: <the strongest emotional or narrative angle>
Why it can work: <one concise reason>
```

The next skill, `intake`, can use this conversational context to write normal `session.json`.

## Hard Rules

- Do not write `research.md`; the `research` skill owns that.
- Do not create or edit `session.json`.
- Do not add `idea`, `idea_selected`, or discovery-specific fields to project config.
- Do not ask production-config questions unless needed to shape idea options.
- Do not generate final narration prose.
