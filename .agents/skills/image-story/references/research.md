# Research Stage

This stage is the **researcher and story archaeologist**. Its only job is to find real and powerful material and persist it for downstream creative work. It does **not** write the story or direct scenes.

---

## When to Run

Run this stage when:
- `session.json` exists with `status: "intake_complete"`
- the user chooses research before composition, or explicitly requests re-research
- `research.md` does not yet exist, or the user asks to re-research

---

## What Good Research Looks Like

The composer and visual orchestrator need more than facts. They need:
- **Real incidents** — things that actually happened, with names, places, dates
- **Surprising truths** — things that make the audience stop and think (*"ऐसा हुआ था क्या?"*)
- **Textured details** — specific sensory and emotional details that bring a scene alive
- **Attributed wisdom** — exact quotes, shlokas, letters, lecture lines, or sayings that carry weight in narration
- **Emotional beats** — human conflict, pauses, silence moments, and emotional turns the composer can later shape into narration
- **Plausible fictional bridges** — things not documented but emotionally true, clearly flagged as creative addition

> [!IMPORTANT]
> The research output is a raw ingredient list for later creative stages. The richer and more specific the material, the more vivid and grounded the script and visual direction can be. Avoid generic summaries. Prefer specific, named, grounded details.

---

## Source Tool

Use the globally available `tavily` skill for Tavily-backed search, extraction, site exploration, and deep research. Read its `SKILL.md` and follow its current commands, authentication, and execution paths. This reference owns the research questions, evidence standards, and project output; it does not duplicate provider mechanics or assume a repository-local Tavily path. Available tools `tavily_research`, `tavily_search`, `tavily_extract` etc..

---

## Research Workflow

### Step 1 — Read the Brief
Parse `library/<project_name>/session.json`. Extract:
- `brief.topic` — what the story is about
- `brief.tone` — the emotional register
- `brief.audience` — who is watching
- `brief.target_duration_seconds` — rough scope for how much material is useful

If `visual.aspect_ratio` is `9:16` or `brief.target_duration_seconds <= 180`, also read `references/research-short.md` and let its scope rules override the general search breadth below.

### Step 2 — Plan Your Searches
Unless the Short reference applies, plan 7-10 targeted queries that cover different angles:
1. **Spiritual/Philosophical:** The sacred texts, parables, or philosophical concepts at the heart of the topic
2. **Real story:** A real person, real event, or real historical incident that illustrates the theme
3. **Emotional paradox:** The counterintuitive truth that makes the theme surprising
4. **Deep detail:** Specific sensory or cultural details that add texture (place names, rituals, objects)
5. **Attributed wisdom:** Exact spoken words — shlokas, proverbs, letters, lectures, or famous dialogue — that carry emotional weight
6. **Emotional beats:** Moments of fear, shame, grief, relief, silence, hesitation, or inner conflict that could become the emotional spine of the script
7. **Anti-Hooks & Open-Loop Mining:** The exact counter-intuitive detail or paradox that can create the opening question, plus later escalation and payoff opportunities. Do not assume fixed timestamps.

### Step 3 — Run the Scripts
Execute your planned queries using the custom CLI scripts. For each result:
- Extract the most specific, named, grounded detail
- Note exact quotes with their source
- Flag anything that is surprising or counterintuitive
- Note any stories that have a strong emotional arc (setup → conflict → turn → resolution)

### Step 4 — Write `research.md`

Write all findings to `library/<project_name>/research.md`. Use this exact structure:

The headings are evidence containers, not content quotas. Leave a section empty when no useful verified material exists. The presence of a quote, fact, bridge, or editorial possibility does not imply that Compose should use it.

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
<!-- Specific counter-intuitive facts, subverted expectations, opening visual
     opportunities, later escalation, and payoff details. Do not assign fixed timestamps. -->

## Textured Details
<!-- Sensory and cultural specifics: smells, objects, sounds, rituals.
     These are what make a scene feel real, not generic.
     Example: "Conch shells (Shankh) were blown at the start of battle.
     The Panchajanya was Krishna's conch — its sound was said to terrify
     even the bravest warriors." -->

## Quotable Lines & Attributed Wisdom
<!-- Exact lines worth narrating directly.
     Include the speaker, context, source URL/book/lecture, verification status,
     and exact wording. These are optional evidence, not script requirements. -->

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
<!-- Advisory only: your evidence-based opinion on what angle is strongest.
     What is the most surprising thing you found?
     What detail would resonate most with the target audience?
     What opening material is available? Do not outline the final script. -->
```

---

## Hard Rules

- **Write for downstream creative stages, not for a general reader.** Every line should provide evidence, texture, conflict, or a grounded creative opportunity that can inform composition or visual direction.
- **Specific beats generic every time.** "A soldier from Lucknow in 1947" beats "an Indian soldier".
- **Always include source URLs** for factual claims so the composer can verify or deepen them.
- **Flag all creative additions** in the "Creative Bridges" section — never mix fiction with fact silently.
- **No story writing in this stage.** Only raw material collection.
- **Research is not a script checklist.** Do not frame optional findings as mandatory inclusions or pre-compose the final structure.
- **Update `session.json`** status to `"research_complete"` after writing `research.md`.
