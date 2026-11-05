# Validation scope

The consolidation was checked locally on macOS using Python 3.12, independent locked environments, isolated homes, mocked provider calls, and blocked external/Flow connections during tests. Both small synthetic fixtures rendered through the actual FFmpeg pipelines without credentials. [The first hosted run](https://github.com/Veer376/video-studio/actions/runs/42001063531) passed all four pipeline/platform jobs on macOS and Linux, including independent locked installs, 102 image tests or 53 video tests, and the corresponding fixture render. [Current CI results](https://github.com/Veer376/video-studio/actions/workflows/checks.yml) track subsequent changes.

Live narration, transcription, image generation, video generation, provider authentication, regional access, billing, and optional Flow/browser integration were intentionally not exercised. Request mocks validate local routing/serialization; they cannot establish remote model quality or account access. The showcase uses existing owned production footage, not new live API validation.

Run from either pipeline:

```bash
uv sync --locked --python 3.12
uv run --locked python ../../tools/check_offline.py
```

The runner removes provider credentials from its process and permits only loopback test connections, excluding the Flow port. The media-server test needs local socket binding. Render examples using each README command; inspect the result rather than treating a zero exit code as visual approval.
