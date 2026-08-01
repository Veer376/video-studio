---
name: youtube
description: Standalone YouTube skill for Story Video Maker. Use when the user asks to upload a library/<project_slug> video, check upload status, list channel uploads, or fetch/attach a YouTube video to a project. Bundles its own youtube.py script and is not part of the main image-story pipeline.
---

# YouTube Skill

This standalone skill handles YouTube upload and lookup tasks for Story Video Maker projects.

## Boundary

Use the bundled script only:

```bash
python3 .agents/skills/youtube/scripts/youtube.py upload library/<project_slug>
python3 .agents/skills/youtube/scripts/youtube.py status library/<project_slug>
python3 .agents/skills/youtube/scripts/youtube.py list
python3 .agents/skills/youtube/scripts/youtube.py fetch <video_id_or_url>
python3 .agents/skills/youtube/scripts/youtube.py compress-thumbnail library/<project_slug>
```

## Inputs

Read:

```text
library/<project_slug>/output/final-video.mp4
library/<project_slug>/youtube/metadata.json
library/<project_slug>/youtube/thumbnails/*.png
library/<project_slug>/youtube/thumbnails/*.jpg
library/<project_slug>/youtube/thumbnails/*.jpeg
```

`metadata.json` comes from `package-youtube` and should contain:

```json
{
  "recommended_title": "",
  "alternate_titles": [],
  "description": ""
}
```

Hashtags should already be inside `description`. Do not invent separate comma tags unless `metadata.json` explicitly contains `tags`.

## Output

Write and update only:

```text
library/<project_slug>/youtube/upload.json
```

Do not create `upload.md`.

## State Rules

`upload.json` is the source of truth.

If `upload.json` does not exist:

1. Read the final MP4.
2. Read `metadata.json`.
3. Resolve the thumbnail: `thumbnail-01` by default, or the user-selected thumbnail.
4. Upload the video through the official YouTube Data API.
5. Set `thumbnail-01` by default, or the user-selected thumbnail when provided.
6. Write `upload.json`.
7. Stop after YouTube accepts the upload and returns `video_id`.

If `upload.json` exists:

1. Do not re-upload.
2. Run status mode.
3. Update `last_checked_at`, `processing_status`, and API response details when available.
4. Re-upload only when the user explicitly asks for force/reupload.

`list` is read-only and writes nothing.

`fetch` is read-only unless `--project library/<project_slug>` is provided. With `--project`, it writes or updates that project's `youtube/upload.json`, which supports attaching a manually uploaded YouTube video to a project.

## Thumbnail Selection

Use `thumbnail-01` by default if the user does not request another thumbnail.

Default selection order:

1. `thumbnail-01.png`
2. `thumbnail-01.jpg`
3. `thumbnail-01.jpeg`

If the user asks for a specific thumbnail, pass:

```bash
--thumbnail thumbnail-02.png
```

The value may be a filename under `youtube/thumbnails/` or a path.

Validate:

- file exists
- extension is `.png`, `.jpg`, or `.jpeg`
- file size is at most 2 MB

If the selected thumbnail is over 2 MB, compress it before upload and use the compressed sibling file. Preserve dimensions by default; use scale only when explicitly requested.

## Visibility

Default visibility is `private` unless the user explicitly requests:

```text
--visibility public
--visibility unlisted
--visibility private
```

Publishing public videos is allowed only when the user explicitly asks for public upload.

## Commands

Upload once:

```bash
python3 .agents/skills/youtube/scripts/youtube.py upload library/<project_slug> --visibility private
```

Upload with a custom thumbnail:

```bash
python3 .agents/skills/youtube/scripts/youtube.py upload library/<project_slug> --thumbnail thumbnail-02.png
```

Upload public when explicitly requested:

```bash
python3 .agents/skills/youtube/scripts/youtube.py upload library/<project_slug> --visibility public
```

Check status after upload:

```bash
python3 .agents/skills/youtube/scripts/youtube.py status library/<project_slug>
```

List recent channel uploads:

```bash
python3 .agents/skills/youtube/scripts/youtube.py list --max-results 10
```

Fetch one YouTube video:

```bash
python3 .agents/skills/youtube/scripts/youtube.py fetch <video_id_or_url>
```

Attach a manually uploaded YouTube video to a project:

```bash
python3 .agents/skills/youtube/scripts/youtube.py fetch <video_id_or_url> --project library/<project_slug>
```

Compress a thumbnail manually:

```bash
python3 .agents/skills/youtube/scripts/youtube.py compress-thumbnail library/<project_slug> --thumbnail thumbnail-02.png --quality 88
```

Use `--scale-percent` only when quality compression is not enough or the user explicitly asks to resize.

Force a new upload:

```bash
python3 .agents/skills/youtube/scripts/youtube.py upload library/<project_slug> --force --visibility private
```

## Hard Rules

- Use only official YouTube Data API calls.
- Do not inspect browser cookies, storage, XHR auth headers, or private Studio endpoints.
- Do not re-upload if `upload.json` exists unless the user explicitly asks for `--force`.
- Do not create `upload.md`.
- Do not create list cache files.
- Do not modify project files except `library/<project_slug>/youtube/upload.json` and derived compressed thumbnails under `library/<project_slug>/youtube/thumbnails/`.
