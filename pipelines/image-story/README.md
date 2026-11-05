# Story Video Maker

A Story Video Maker workspace with two clear layers:

1. **Project-owned pipeline code**
   - Located in `src/`.
   - The older deterministic manifest renderer is preserved.
   - The new `src/studio/` package owns the resumable `library/<slug>` production pipeline.

2. **Agent-facing creative skills**
   - Located in `.agents/skills/`.
   - `image-story` owns intake, research, splitting, production, packaging, and publishing through stage references.
   - `compose` and `orchestrate-visuals` remain focused creative skills.

## Pipeline CLI

Inspect a project:

```bash
story-video status library/<project_name>
```

Run or resume the default production flow:

```bash
story-video run library/<project_name>
```

Run one stage:

```bash
story-video stage voice library/<project_name>
story-video stage illustrate library/<project_name>
story-video stage render library/<project_name>
```

Illustration can also run its two resumable phases independently:

```bash
story-video stage illustrate library/<project_name> --illustration-phase characters
story-video stage illustrate library/<project_name> --illustration-phase scenes
```

Default stage behavior is missing-only. For example:

```bash
story-video stage illustrate library/<project_name>
```

generates only missing character and scene images. To regenerate all character and scene images:

```bash
story-video stage illustrate library/<project_name> --force
```

## New Studio Layout

```text
src/studio/
├── core/                 # session, paths, state, validation helpers
├── scripts/              # reusable production capabilities
└── pipeline_scripts/     # ordered flows that compose scripts
```

## Naming Contract

```text
Story Video Maker          product/repository name
image-story                master workflow Codex skill
story-video                production CLI executable
```

Default production flow:

```text
voice -> illustrate -> render
```

Cloudflare is the only image backend for now. Provider abstraction can be added later without changing the pipeline contract.

---

## Key Patterns & Robustness

The codebase is built to be resilient, particularly in resource generation and API interaction. Taking `src/audio/gemini.py` as a reference, the following architectural patterns are used:

- **Round-Robin API Key Rotation:** Distributes request loads across multiple environment API keys (`GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, etc.) sequentially to avoid hitting rate limits.
- **Resilient Connection Retries:** Implements automatic request retries (up to 5 times) with exponential backoff for network/DNS failures (`URLError`) and retryable HTTP status codes (e.g., `429`, `500`, `503`).
- **Fail-Safe Error Serialization:** Logs detailed error logs to disk (`errors/audio/`) upon reaching maximum retries, capturing HTTP/URL details, execution context, and masked API credentials for debugging.
- **SSL Verification Fallback:** Transparently catches SSL cert verification failures and falls back to an unverified context to guarantee execution across varied local development environments.
