# Setup

## System requirements

Use a source checkout, Python 3.12, uv, FFmpeg/FFprobe, and a writable project directory. The tools resolve assets relative to their owning pipeline; run commands from that pipeline directory. Environments are independent: do not combine the two lockfiles or activate one pipeline's environment for the other.

macOS with Homebrew:

```bash
brew install uv ffmpeg
uv python install 3.12
```

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg fonts-noto-core
```

Install uv using its [official installation instructions](https://docs.astral.sh/uv/getting-started/installation/), then `uv python install 3.12`. Pillow's packaged wheels provide the renderer; complex-script subtitles require a shaping-capable build and matching font. On Linux, `fonts-noto-core` supplies Noto Sans Devanagari. A project-local `assets/fonts/Devanagari.ttf` overrides detection; only redistribute fonts with appropriate permission.

Run `uv sync --locked --python 3.12` inside each selected pipeline. This downloads dependencies but does not call a generation provider. Browser/Playwright dependencies are optional and unnecessary for the documented direct-API and offline paths.

## Image-story credentials

From `pipelines/image-story`:

```bash
cp .env.example .env
# Edit .env with your own keys.
export STUDIO_ENV_FILE="$PWD/.env"
```

The maintained image commands load only this explicitly selected file. Exported environment values take precedence. There is no implicit personal home-directory credential file. The loader accepts simple `NAME=value` lines, comments, and quoted values; it is not a shell interpreter.

| Stage | Configuration |
| --- | --- |
| Narration | `GEMINI_API_KEY`; optional `GEMINI_TTS_MODEL` and `GEMINI_TTS_VOICE` |
| Transcription | `GROQ_API_KEY` for Whisper Large V3; optional `OPENAI_API_KEY` enables Whisper-1 fallback after failed/invalid Groq output |
| Images | `GEMINI_API_KEY` for Google Developer API; ADC plus a Cloud project is an alternative when no API key is set |
| Optional image-story video | Same Google credentials; explicit authored video prompt map required |
| Flow | Separate local service plus browser extension/session; `FLOW_AGENT_URL` selects its address |

If only `OPENAI_API_KEY` is supplied for transcription, it is used directly. Leaving it unset disables paid OpenAI fallback. Narration can attempt more than one configured Gemini key after a failure; use one key for the simplest setup. Each attempted provider request can consume quota.

## Generated-video credentials

From `pipelines/generated-video`, export a key in the current shell:

```bash
export GEMINI_API_KEY='YOUR_KEY'
```

`.env.example` lists variables but the generated-video commands do not automatically load `.env`. Keep credentials outside tracked files. The Google adapter prefers an explicit `GEMINI_API_KEY`/`GOOGLE_API_KEY`; otherwise it can use separately configured Google Cloud Application Default Credentials and `GOOGLE_CLOUD_PROJECT`/`GCP_PROJECT_ID`. Developer API model IDs and Vertex model availability can differ; the example targets Developer API access.

## Provider access

Create credentials and enable billing/model access in the provider's console before running generation. Local validation cannot prove your account's model availability. Current configured defaults are Gemini `gemini-3.1-flash-image`, `gemini-3.1-flash-tts-preview`, and `gemini-omni-1.1-flash`. Google video requests use the Interactions API, inline MP4 output, requested clip duration, and 720p output. Inspect the generated clip before acceptance; requested duration is not a measured result.

See [Google image generation](https://ai.google.dev/gemini-api/docs/image-generation), [speech generation](https://ai.google.dev/gemini-api/docs/speech-generation), [Omni video generation](https://ai.google.dev/gemini-api/docs/omni), [Groq transcription](https://console.groq.com/docs/speech-to-text), and provider pricing/access pages. These are external services; no hosted account or credits are included.

## Optional Flow

Flow is not included in this repository. It requires a compatible `flow-agent` HTTP service, its Chrome extension, an authenticated Google Flow browser session, and provider credits. The image adapter expects the service contract used by its implementation; the generated-video adapter supports `--provider flow --flow-host 127.0.0.1:8001`. This is an advanced compatibility path, not required setup. Some Flow inputs can route to Google fallback; inspect the dry-run routing before running and configure Google access if that route is needed. No Flow integration was live-validated for this release.

## Certificates and troubleshooting

Maintained image HTTP clients verify TLS certificates using certifi; `SSL_CERT_FILE` can select an organization-provided CA bundle. Fix a missing/trusted CA problem rather than disabling verification. Missing FFmpeg, invalid input JSON, incomplete timings, missing assets, stale fingerprints, and unaccepted video reviews fail before final rendering; see [recovery](recovery.md).
