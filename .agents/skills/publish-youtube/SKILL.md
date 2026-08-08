---
name: publish-youtube
description: Story Video Maker YouTube publishing skill. Use when the user asks to publish, upload, check status, attach a manually uploaded video, or compress/select thumbnails for a library/<project_name> project. Reads project output, package-youtube metadata, and thumbnails; uses the generic youtube skill API layer; writes library/<project_name>/youtube/upload.json.
---

# Publish YouTube Skill

Use this skill for Story Video Maker project publishing. It is the project-aware layer over the generic `youtube` API skill.

Run the bundled CLI:

```bash
python3 .agents/skills/publish-youtube/scripts/publish_youtube.py <command>
```

## Commands

Publish a project:

```bash
python3 .agents/skills/publish-youtube/scripts/publish_youtube.py publish library/<project_name> --visibility private
```

Check an existing project upload:

```bash
python3 .agents/skills/publish-youtube/scripts/publish_youtube.py status library/<project_name>
```

Attach a video uploaded manually in YouTube Studio:

```bash
python3 .agents/skills/publish-youtube/scripts/publish_youtube.py attach library/<project_name> <video_id_or_url>
```

Compress a project thumbnail:

```bash
python3 .agents/skills/publish-youtube/scripts/publish_youtube.py compress-thumbnail library/<project_name> --thumbnail thumbnail-02.png
```

## Inputs

Read:

```text
library/<project_name>/output/final-video.mp4
library/<project_name>/youtube/metadata.json
library/<project_name>/youtube/thumbnails/*.png
library/<project_name>/youtube/thumbnails/*.jpg
library/<project_name>/youtube/thumbnails/*.jpeg
```

`metadata.json` should come from `package-youtube` and include:

```json
{
  "recommended_title": "",
  "alternate_titles": [],
  "description": ""
}
```

Hashtags should already be inside `description`. Use explicit `tags` only when present in `metadata.json`.

## Outputs

Write only:

```text
library/<project_name>/youtube/upload.json
derived compressed thumbnails under library/<project_name>/youtube/thumbnails/
```

Do not create `upload.md`.

## Rules

- Do not re-upload when `upload.json` exists unless the user explicitly requests `--force`.
- Default visibility is `private`.
- Use `--visibility public` only when the user explicitly asks for public publishing.
- Use `thumbnail-01` by default unless the user requests another thumbnail.
- Compress thumbnails over the YouTube upload limit before setting them.
- Use official YouTube APIs through the generic `youtube` skill modules only.
