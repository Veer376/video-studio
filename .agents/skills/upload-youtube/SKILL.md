---
name: upload-youtube
description: Standalone YouTube upload skill for Story Video Maker. Use when the user asks to upload an existing library/<project_slug> video to YouTube using metadata and thumbnails from library/<project_slug>/youtube/. Bundles its own upload script, writes upload state only to upload.json, and is not part of the main image-story pipeline.
---

# Upload YouTube Skill

This skill uploads a prepared Story Video Maker project to YouTube. It is standalone skill.

## Boundary

Use the bundled script only:

```bash
python3 .agents/skills/upload-youtube/scripts/upload_youtube.py upload library/<project_slug>
python3 .agents/skills/upload-youtube/scripts/upload_youtube.py status library/<project_slug>
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
3. Choose the best thumbnail.
4. Upload the video through the official YouTube Data API.
5. Set the thumbnail when available.
6. Write `upload.json`.
7. Stop after YouTube accepts the upload and returns `video_id`.

If `upload.json` exists:

1. Do not re-upload.
2. Run status mode.
3. Update `last_checked_at`, `processing_status`, and API response details when available.
4. Re-upload only when the user explicitly asks for force/reupload.

## Thumbnail Selection

Choose the thumbnail in this order:

1. `thumbnail-01.png`
2. `thumbnail-01.jpg`
3. `thumbnail-01.jpeg`
4. first valid image in `youtube/thumbnails/`

Validate:

- file exists
- extension is `.png`, `.jpg`, or `.jpeg`
- file size is at most 2 MB

If no valid thumbnail exists, **flag** this to the user.

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
python3 .agents/skills/upload-youtube/scripts/upload_youtube.py upload library/<project_slug> --visibility private
```

Upload public when explicitly requested:

```bash
python3 .agents/skills/upload-youtube/scripts/upload_youtube.py upload library/<project_slug> --visibility public
```

Check status after upload:

```bash
python3 .agents/skills/upload-youtube/scripts/upload_youtube.py status library/<project_slug>
```

Force a new upload:

```bash
python3 .agents/skills/upload-youtube/scripts/upload_youtube.py upload library/<project_slug> --force --visibility private
```

## Hard Rules

- Use only official YouTube Data API calls.
- Do not inspect browser cookies, storage, XHR auth headers, or private Studio endpoints.
- Do not re-upload if `upload.json` exists unless the user explicitly asks for `--force`.
- Do not create `upload.md`.
- Do not modify files outside `library/<project_slug>/youtube/upload.json` during normal operation.
