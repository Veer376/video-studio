# Story Video Maker

A dual-purpose workspace combining a robust rendering engine with agentic skills for automated story video creation.

## 📖 Dual Nature of the Project

This project functions in two distinct ways:

1. **Deterministic Render Engine (CLI)**
   - Located in the `src/` directory.
   - A Python CLI (`cli:main`) that parses video manifests (`story.json`), fetches and paces TTS audio narration, validates assets, and compiles scenes (images + audio) into structured MP4 videos via `ffmpeg`.

2. **AI Agent Content Generation & Skills**
   - Configured in the `.agents/skills/` directory.
   - Equips AI agents with structured workflows (`interview-story-config`, `content-creator`, `story-video-producer`) to interview creators, research stories, and generate production-ready assets.
   - Generated content sessions are structured and stored dynamically inside the `library/` directory.

---

## 🛠️ Key Patterns & Robustness

The codebase is built to be resilient, particularly in resource generation and API interaction. Taking `src/audio/gemini.py` as a reference, the following architectural patterns are used:

- **Round-Robin API Key Rotation:** Distributes request loads across multiple environment API keys (`GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, etc.) sequentially to avoid hitting rate limits.
- **Resilient Connection Retries:** Implements automatic request retries (up to 5 times) with exponential backoff for network/DNS failures (`URLError`) and retryable HTTP status codes (e.g., `429`, `500`, `503`).
- **Fail-Safe Error Serialization:** Logs detailed error logs to disk (`errors/audio/`) upon reaching maximum retries, capturing HTTP/URL details, execution context, and masked API credentials for debugging.
- **SSL Verification Fallback:** Transparently catches SSL cert verification failures and falls back to an unverified context to guarantee execution across varied local development environments.
