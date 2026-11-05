# Log Project Insight

Record an insight only when the user explicitly asks to log, save, or record it. Do not write merely because an important observation appears or this prompt is read.

1. Locate the repository root and read `insights.md` completely. If it does not exist, create it with `# Project Insights` only when an insight is being logged.
2. Derive the durable insight from the user's request and the evidence in the current context. An insight should improve future project decisions or agent behavior; it is not a todo, status update, transcript, or speculative claim.
3. Compare it with every related existing entry:
   - if already captured, make no change;
   - if it corrects or strengthens an entry, replace that entry with one consolidated final insight;
   - if distinct, append it.
4. Preserve the most accurate current conclusion, its essential reasoning, and its practical implication. Remove duplicated wording and obsolete conclusions rather than preserving decision history.
5. Change only `insights.md`, then report whether the insight was added, consolidated, or already present.
