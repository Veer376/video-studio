# Character readiness

Use this reference before scene prompting when a recurring character must remain visually consistent.

## Readiness gate

Register only characters whose identity must persist across clips. Describe one-off figures directly in the scene prompt.

Resolve each required `@handle` from the selected production root's registry first, then the studio registry. A character is ready when the resolved entry has a name, an existing reference image, and a complete profile. A production override may inherit profile and description from its studio entry.

## Field ownership

- `profile` is concise, stable, model-facing grounding used across clips. Include only facts that materially help preserve identity or performance: age or scale, build, non-standard anatomy, voice, movement, and stable behavioral traits. Add identity-critical wardrobe or fixed props only when the reference image alone may not communicate them reliably.
- `description` is concise narrative context: role, relationships, and motivation. Do not use it for physical grounding.
- `reference_path` points to the approved canonical image that owns the character's visible design.

For standard subjects, keep the profile minimal. For non-standard or hybrid subjects, state the structural facts that ordinary world knowledge cannot supply, including explicit exclusions only when they prevent a plausible anatomical mistake.

Do not put scene-specific actions, temporary emotions, temporary wardrobe, or current plot state in either field.

## Missing character

When a required character is not ready:

1. Derive its identity only from approved story facts and existing project context. Ask the user when an unresolved choice would materially change the design.
2. Create one production-ready reference by default. Use the interactive `prompts/create-characters.md` workflow only when the user requests variants or design exploration.
3. Generate the image through `/flow`. Follow the selected story's visual contract and any applicable shared-universe asset standard.
4. Inspect the result for the intended identity, readable anatomy and silhouette, required fixed features, and suitability as a clean video reference.
5. Save reusable characters under studio assets and production-specific characters under the selected production root. Register the canonical repository-relative path and the complete field contract in the owning registry.

Do not begin the scene prompt until every required recurring character passes the readiness gate.
