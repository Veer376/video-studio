# Generated video

Directed scene inputs → generated motion clips → human review → accepted sequence. Direct Google API generation is primary; Flow is an optional service adapter. The creative workflow is available in `.agents/skills/produce-story` and `.agents/skills/compile-omni-scene`.

## Install and render the offline example

From this directory:

```bash
uv sync --locked --python 3.12
uv run --locked python -m scripts.render_video --config examples/offline/scenes.json --dry-run
uv run --locked python -m scripts.render_video --config examples/offline/scenes.json --output output/offline.mp4
```

Requires FFmpeg/FFprobe. Output: `output/offline.mp4` (two 4-second synthetic color/tone clips). The committed fixture reviews and contact sheets bind to the actual fixture hashes. No model calls or credentials are needed.

## Create and generate a production

Configure `GEMINI_API_KEY` using [setup](../../docs/setup.md), then:

```bash
uv run --locked python -m scripts.new_project my-story
uv run --locked python -m scripts.generate_scenes --config work/my-story/scenes.json --dry-run
```

Edit `work/my-story/story.md`, `characters.json`, and `scenes.json` before generation. The scene template contains simple prompts with no recurring identities. Its output paths are rewritten for the new production. The config owns model/aspect ratio/duration and an ordered scene list; each scene owns its prompt, reference/subject handles, optional predecessor reference, and active clip output path. Relative output paths are relative to this pipeline directory, not the config directory. Reference registries are resolved by the scene compiler.

Generate one scene, inspect/review it, then continue sequentially:

```bash
uv run --locked python -m scripts.generate_scenes --config work/my-story/scenes.json --scene s001 --provider google
```

This command is billable. Model/account access is required and was not live-tested for this release. The default is `gemini-omni-1.1-flash`; select a currently available model in your config. Each successful generation creates a hash-bound `pending_review` record. Existing active clips are not automatically accepted or overwritten.

## Review and accept

Watch and listen to the complete active clip. Compare it against the authored scene and predecessor continuity. Inspect duration, video/audio streams, dimensions and frame rate:

```bash
ffprobe -v error -show_streams -show_format work/my-story/videos/s001.mp4
mkdir -p work/my-story/temp/contact_sheets
ffmpeg -y -i work/my-story/videos/s001.mp4 -vf 'fps=1,scale=320:-1,tile=4x3' -frames:v 1 work/my-story/temp/contact_sheets/s001.png
```

For longer clips, adapt the contact-sheet grid/sample rate so all time is covered. Read the [review contract](.agents/skills/produce-story/references/clip-review.md). After inspection, edit the generated `reviews/s001.json`: set a justified decision (`accepted`, `accepted_with_note`, or `fix_next_scene`), `media_valid: true`, the pipeline-relative `contact_sheet_path`, observed `findings`, and `diagnosis`. Preserve the generated `video_path`, `video_sha256`, and history; do not replace the hash to conceal modified media. Use `needs_fix` for unusable results. The review record is a human/agent-authored judgment; the scripts validate its binding and required evidence, not creative correctness.

Repeat generation and review for the next scene. Then:

```bash
uv run --locked python -m scripts.render_video --config work/my-story/scenes.json --dry-run
uv run --locked python -m scripts.render_video --config work/my-story/scenes.json
```

Output: `work/my-story/output/final-video.mp4`. Rendering rejects missing, stale, unaccepted, or incompatible clips. [Recovery](../../docs/recovery.md) explains diagnosed replacement generation, archive limits, and restoration. Real productions belong in ignored `work/`, not the public examples.
