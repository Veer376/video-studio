# Video Pipeline Instructions — Extension

## Required workflow

- **Clip review (subagent available)**: Use a subagent for the clip review process. Ask it to meticulously scan the contact sheet, flag every visual inconsistency, and persist its findings in the scene's review JSON. Agent should explicitly log any minor visual variance (even harmless ones marked accepted_with_note) so downstream prompts can actively avoid compounding drift. Provide detailed instructions to the agent.
- **Clip review (no subagent)**: Read `.agents/skills/produce-story/references/clip-review.md` in full. Inspect the contact sheet, first/final frames, and dense frame extractions directly. Check character identity, counts, props, actions, and continuity against the scene contract. Log all findings and minor visual variances (including `accepted_with_note`) in `reviews/<scene-id>.json` before continuing or replacing the video.