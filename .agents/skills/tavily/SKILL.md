---
name: tavily
description: Tavily web-source capability skill. Use when you need Tavily-backed search, URL extraction, site mapping, site crawling, or async deep research for any workflow.
---

# Tavily

## Overview

Use this skill as the shared Tavily provider layer. It does not own story, project, YouTube, or pipeline semantics; higher-level skills decide why to search and how to use the results.

The CLI loads `TAVILY_API_KEY` from the environment or `~/.config/projects/.env`.

## Commands

Run from the repository root:

```bash
python3 .agents/skills/tavily/scripts/tavily.py search --query "<query>"
python3 .agents/skills/tavily/scripts/tavily.py extract --urls "<url1,url2>"
python3 .agents/skills/tavily/scripts/tavily.py map --url "<site-url>"
python3 .agents/skills/tavily/scripts/tavily.py crawl --url "<site-url>" --max-depth 1 --max-pages 5
python3 .agents/skills/tavily/scripts/tavily.py research --query "<research brief>"
```

Use `--out <path>` on any command to write JSON to disk. Otherwise the command prints JSON to stdout.

## Search

Use `search` for first-pass discovery and source finding:

```bash
python3 .agents/skills/tavily/scripts/tavily.py search \
  --query "Vivekananda fear quote source" \
  --search-depth advanced \
  --topic general \
  --max-results 8
```

Controls:

- `--search-depth basic|advanced`
- `--topic general|news|finance`
- `--max-results <n>`
- `--include-raw-content`

## Extract

Use `extract` after choosing URLs from search/map/crawl:

```bash
python3 .agents/skills/tavily/scripts/tavily.py extract \
  --urls "https://example.com/a,https://example.com/b"
```

## Map And Crawl

Use `map` to discover relevant URLs on a site without reading every page:

```bash
python3 .agents/skills/tavily/scripts/tavily.py map --url "https://example.com"
```

Use `crawl` when a site is likely valuable and bounded exploration is needed:

```bash
python3 .agents/skills/tavily/scripts/tavily.py crawl \
  --url "https://example.com" \
  --max-depth 1 \
  --max-pages 5
```

Keep crawls small unless the user explicitly asks for broad crawling.

## Deep Research

Use `research` for multi-step Tavily synthesis when the topic is broad or ambiguous:

```bash
python3 .agents/skills/tavily/scripts/tavily.py research \
  --query "Short Hindi story ideas based on Vivekananda teachings for young adults" \
  --model mini
```

Controls:

- `--model mini|standard`
- `--poll-interval <seconds>`
- `--max-polls <n>`

## Result Handling

- Treat Tavily output as source material, not final truth.
- Prefer exact URLs, dates, names, and quotes from source pages.
- Run `extract` on important URLs before relying on details.
- Label weak evidence or AI-synthesized research clearly in downstream outputs.
- Do not copy source text into final scripts except short attributed quotes.
