---
name: research
description: Content discovery skill. Runs after intake. Searches the web for real stories, historical facts, spiritual sources, and surprising angles related to the brief, then writes everything to research.md — formatted specifically to help the compose skill write a richer, more emotionally resonant script.
---

# Research Skill

This skill is a **researcher and story archaeologist**. Its only job is to go outside, find real and powerful material, and bring it back in a format that makes the composer's job easier. It does **not** write any story. It collects raw material.

---

## When to Activate

Activate this skill when:
- `session.json` exists with `status: "intake_complete"`
- `research.md` does not yet exist, or the user asks to re-research

---

## What Good Research Looks Like

The composer needs more than facts. They need:
- **Real incidents** — things that actually happened, with names, places, dates
- **Surprising truths** — things that make the audience stop and think (*"ऐसा हुआ था क्या?"*)
- **Textured details** — specific sensory and emotional details that bring a scene alive
- **Quotes and shlokas** — exact spoken words that carry weight in narration
- **Plausible fictional bridges** — things not documented but emotionally true, clearly flagged as creative addition

> [!IMPORTANT]
> The research output is the raw ingredient list for the composer. The richer and more specific the material, the more vivid and original the script will be. Avoid generic summaries. Prefer specific, named, grounded details.

---

## Available CLI Tools

You have four custom Tavily CLI tools located in `.agents/skills/research/scripts/`. They automatically handle API authentication from your home configuration (`~/.config/story-video-maker/.env`) and return results in structured JSON format. 

Use the `run_command` tool to execute them:

### Tool 1 — `/search` (Primary Discovery)
Perform web searches with adjustable depth, classification topic, and results count.

```bash
# Basic usage
python3 .agents/skills/research/scripts/tavily_search.py --query "Krishna Arjuna Bhagavad Gita karma lesson"

# Advanced search with news focus and raw HTML retrieval
python3 .agents/skills/research/scripts/tavily_search.py --query "motivational karma paradox" --search-depth advanced --topic news --max-results 3 --include-raw-content
```

---

### Tool 2 — `/extract` (Deep Page Reading)
Retrieve clean, reader-mode content for specific URLs.

```bash
python3 .agents/skills/research/scripts/tavily_extract.py --urls "https://www.wisdomlib.org/hinduism/book/mahabharata,https://example.com/article"
```

---

### Tool 3 — `/crawl` + `/map` (Site Exploration)
Map a site's structure or recursively crawl multiple pages to gather content.

```bash
# Discover URLs on a site (map mode)
python3 .agents/skills/research/scripts/tavily_crawl.py --url "https://www.ramakrishnavivekananda.info" --mode map

# Crawl and extract from up to 5 pages
python3 .agents/skills/research/scripts/tavily_crawl.py --url "https://www.wisdomlib.org/hinduism/book/shrimad-bhagavad-gita" --mode crawl --max-depth 1 --max-pages 5
```

---

### Tool 4 — `/research` (Deep Synthesis)
Execute an end-to-end multi-step research task and output a compiled report. (This is async; the script automatically polls for status).

```bash
python3 .agents/skills/research/scripts/tavily_research.py --query "scientific basis of action preceding motivation neuroscience"
```

---

## Research Workflow

### Step 1 — Read the Brief
Parse `library/<project_slug>/session.json`. Extract:
- `brief.topic` — what the story is about
- `brief.theme` — the core keyword
- `brief.tone` — the emotional register
- `brief.audience` — who is watching

### Step 2 — Plan Your Searches
Before running any command, plan 4–6 targeted queries that cover different angles:
1. **Spiritual/Philosophical:** The sacred texts, parables, or philosophical concepts at the heart of the topic
2. **Real story:** A real person, real event, or real historical incident that illustrates the theme
3. **Emotional paradox:** The counterintuitive truth that makes the theme surprising
4. **Deep detail:** Specific sensory or cultural details that add texture (place names, rituals, objects)
5. **Quotes:** Exact spoken words — shlokas, proverbs, famous dialogue — that carry emotional weight

### Step 3 — Run the Scripts
Execute your planned queries using the custom CLI scripts. For each result:
- Extract the most specific, named, grounded detail
- Note exact quotes with their source
- Flag anything that is surprising or counterintuitive
- Note any stories that have a strong emotional arc (setup → conflict → turn → resolution)

### Step 4 — Write `research.md`

Write all findings to `library/<project_slug>/research.md`. Use this exact structure:

```markdown
# Research: <topic>
Generated: <date>
Source: <session.json project_slug>

---

## Real Incidents & Named Stories
<!-- Specific real events, people, places with source URLs.
     Prefer: named individuals, specific dates, specific locations.
     Example: "In 1947, a 19-year-old soldier from Lucknow..." -->

## Spiritual & Philosophical Sources
<!-- Exact shlokas, parables, or teachings with translations.
     Example: "Gita 2.47 — कर्मण्येवाधिकारस्ते..." -->

## Surprising Truths & Paradoxes
<!-- The counterintuitive angles. What would make the audience stop.
     Example: "Modern neuroscience confirms that motivation follows action,
     not the other way around — exactly what Krishna taught 5000 years ago." -->

## Textured Details
<!-- Sensory and cultural specifics: smells, objects, sounds, rituals.
     These are what make a scene feel real, not generic.
     Example: "Conch shells (Shankh) were blown at the start of battle.
     The Panchajanya was Krishna's conch — its sound was said to terrify
     even the bravest warriors." -->

## Powerful Quotes
<!-- Exact spoken words worth narrating directly.
     Include the speaker, context, and source. -->

## Creative Bridges (Plausible Fiction)
<!-- Things that are emotionally true but not documented.
     Clearly flagged as creative additions.
     Example: "It is easy to imagine that Arjuna had not slept the
     night before — that he had walked among the tents of his cousins..." -->

## What the Composer Should Emphasise
<!-- Your editorial opinion on what angle is strongest.
     What is the most surprising thing you found?
     What detail would resonate most with the target audience?
     What should the script open with? -->
```

---

## Hard Rules

- **Write for the composer, not for a reader.** Every line in `research.md` should be something a scriptwriter can directly use, reference, or be inspired by.
- **Specific beats generic every time.** "A soldier from Lucknow in 1947" beats "an Indian soldier".
- **Always include source URLs** for factual claims so the composer can verify or deepen them.
- **Flag all creative additions** in the "Creative Bridges" section — never mix fiction with fact silently.
- **No story writing in this skill.** Only raw material collection.
- **Update `session.json`** status to `"research_complete"` after writing `research.md`.
