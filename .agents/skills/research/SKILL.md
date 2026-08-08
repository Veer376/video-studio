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
- **Attributed wisdom** — exact quotes, shlokas, letters, lecture lines, or sayings that carry weight in narration
- **Emotional beats** — human conflict, pauses, silence moments, and emotional turns the composer can later shape into narration
- **Plausible fictional bridges** — things not documented but emotionally true, clearly flagged as creative addition

> [!IMPORTANT]
> The research output is the raw ingredient list for the composer. The richer and more specific the material, the more vivid and original the script will be. Avoid generic summaries. Prefer specific, named, grounded details.

---

## Available Source Tools

For Tavily-backed source work, use the `tavily` skill. It owns the provider commands and loads API authentication from `~/.config/projects/.env`.

Use the `run_command` tool to execute them:

### Tool 1 — `search` (Primary Discovery)
Perform web searches with adjustable depth, classification topic, and results count.

```bash
# Basic usage
python3 .agents/skills/tavily/scripts/tavily.py search --query "Krishna Arjuna Bhagavad Gita karma lesson"

# Advanced search with news focus and raw HTML retrieval
python3 .agents/skills/tavily/scripts/tavily.py search --query "motivational karma paradox" --search-depth advanced --topic news --max-results 3 --include-raw-content
```

---

### Tool 2 — `extract` (Deep Page Reading)
Retrieve clean, reader-mode content for specific URLs.

```bash
python3 .agents/skills/tavily/scripts/tavily.py extract --urls "https://www.wisdomlib.org/hinduism/book/mahabharata,https://example.com/article"
```

---

### Tool 3 — `crawl` + `map` (Site Exploration)
Map a site's structure or recursively crawl multiple pages to gather content.

```bash
# Discover URLs on a site (map mode)
python3 .agents/skills/tavily/scripts/tavily.py map --url "https://www.ramakrishnavivekananda.info"

# Crawl and extract from up to 5 pages
python3 .agents/skills/tavily/scripts/tavily.py crawl --url "https://www.wisdomlib.org/hinduism/book/shrimad-bhagavad-gita" --max-depth 1 --max-pages 5
```

---

### Tool 4 — `research` (Deep Synthesis)
Execute an end-to-end multi-step research task and output a compiled report. (This is async; the script automatically polls for status).

```bash
python3 .agents/skills/tavily/scripts/tavily.py research --query "scientific basis of action preceding motivation neuroscience"
```

---

## Research Workflow

### Step 1 — Read the Brief
Parse `library/<project_name>/session.json`. Extract:
- `brief.topic` — what the story is about
- `brief.tone` — the emotional register
- `brief.audience` — who is watching
- `brief.target_duration_seconds` — rough scope for how much material is useful

If the user says this research follows discovery, or if `.agents/skills/discovery/research.md` exists and is relevant, read it as optional directional context. Use its selected idea, shortlisted angle, demand signals, sources, and "Next research needed" notes to focus the project research. Do not overwrite discovery's scratchpad.

### Step 2 — Plan Your Searches
Before running any command, plan 7-10 targeted queries that cover different angles:
1. **Spiritual/Philosophical:** The sacred texts, parables, or philosophical concepts at the heart of the topic
2. **Real story:** A real person, real event, or real historical incident that illustrates the theme
3. **Emotional paradox:** The counterintuitive truth that makes the theme surprising
4. **Deep detail:** Specific sensory or cultural details that add texture (place names, rituals, objects)
5. **Attributed wisdom:** Exact spoken words — shlokas, proverbs, letters, lectures, or famous dialogue — that carry emotional weight
6. **Emotional beats:** Moments of fear, shame, grief, relief, silence, hesitation, or inner conflict that could become the emotional spine of the script
7. **Anti-Hooks & Open-Loop Mining:** The exact counter-intuitive detail or paradox that subverts assumptions in the first 15 seconds, plus tension peaks for 45-60s micro open loops.

When discovery context is available, prefer focused verification and enrichment over broad re-discovery. Do not independently change the chosen idea, hook, or emotional direction unless the user asks to reconsider it.

### Step 3 — Run the Scripts
Execute your planned queries using the custom CLI scripts. For each result:
- Extract the most specific, named, grounded detail
- Note exact quotes with their source
- Flag anything that is surprising or counterintuitive
- Note any stories that have a strong emotional arc (setup → conflict → turn → resolution)

### Step 4 — Write `research.md`

Write all findings to `library/<project_name>/research.md`. Use this exact structure:

```markdown
# Research: <topic>
Generated: <date>
Source: <session.json project_name>

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

## Anti-Hooks & Open-Loop Mining
<!-- Specific counter-intuitive facts, subverted expectations, or shocking details
     to be used for the 0:00-0:15 intro hook and 45-60s tension peaks. -->

## Textured Details
<!-- Sensory and cultural specifics: smells, objects, sounds, rituals.
     These are what make a scene feel real, not generic.
     Example: "Conch shells (Shankh) were blown at the start of battle.
     The Panchajanya was Krishna's conch — its sound was said to terrify
     even the bravest warriors." -->

## Quotable Lines & Attributed Wisdom
<!-- Exact lines worth narrating directly.
     Include the speaker, context, source URL/book/lecture if available,
     and why this quote belongs in the story.
     Prefer quotes that deepen the conflict, reveal the turn, or land the final wisdom. -->

## Emotional Beats, Human Conflict & Silence Moments
<!-- Raw emotional material for the composer.
     Capture where the story should breathe, pause, hurt, or turn.
     Prefer concrete beats:
     - "A silent moment before Arjuna speaks, because the battlefield is full of relatives."
     - "The shame is not cowardice; it is the fear of doing the right thing at unbearable cost."
     Do not write final narration or voice directions here. -->

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
- **Preserve confirmed discovery direction** when research follows discovery; deepen it rather than replacing it.
- **Update `session.json`** status to `"research_complete"` after writing `research.md`.
