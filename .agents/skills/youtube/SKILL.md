---
name: youtube
description: General YouTube API skill for authentication, channel confirmation, public search, video fetch, channel lookup, playlist lookup, comments, caption-track lookup, and generic local video upload. Use when Codex needs YouTube platform/data access or to upload any local video file. For Story Video Maker library/<project_slug> publishing, use publish-youtube instead.
---

# YouTube Skill

Use the bundled CLI as the YouTube platform/API layer:

```bash
python3 .agents/skills/youtube/scripts/youtube.py <command>
```

## Boundary

This skill owns generic YouTube API capability:

- `auth`, `whoami`
- `search`, `fetch`, `channel`, `playlist`, `comments`, `transcript`
- `upload-file` for any local video path

It does not own Story Video Maker project publishing semantics. For `library/<project_slug>` publishing, use `publish-youtube`.

## Core Commands

Authenticate or switch channel:

```bash
python3 .agents/skills/youtube/scripts/youtube.py auth --reset --scope all
python3 .agents/skills/youtube/scripts/youtube.py whoami
```

Search YouTube:

```bash
python3 .agents/skills/youtube/scripts/youtube.py search "vivekananda hindi motivation" --max-results 50
```

Fetch one video:

```bash
python3 .agents/skills/youtube/scripts/youtube.py fetch https://youtu.be/<video_id>
```

Fetch owner-only processing status when appropriate:

```bash
python3 .agents/skills/youtube/scripts/youtube.py fetch <video_id_or_url> --processing-details
```

Default `fetch` uses public-safe parts only. `--processing-details` requests owner-only `processingDetails`; if YouTube blocks it for a public/competitor video, retry with public-safe parts and print a warning.

Inspect a channel:

```bash
python3 .agents/skills/youtube/scripts/youtube.py channel @kathamindhindi
```

List playlist videos:

```bash
python3 .agents/skills/youtube/scripts/youtube.py playlist <playlist_id> --max-results 50
```

Fetch comments:

```bash
python3 .agents/skills/youtube/scripts/youtube.py comments <video_id_or_url> --max-results 50
```

Fetch transcript text:

```bash
python3 .agents/skills/youtube/scripts/youtube.py transcript <video_id_or_url> --language hi
```

`transcript` first attempts official YouTube Data API caption-track lookup. If the official API blocks the request or has no usable transcript text, it falls back to `youtube-transcript-api` for public player transcripts unless `--no-fallback` is passed. Label fallback output as `source public_player_fallback`.

Upload any local video:

```bash
python3 .agents/skills/youtube/scripts/youtube.py upload-file /path/to/video.mp4 \
  --title "Title" \
  --description "Description" \
  --thumbnail /path/to/thumbnail.png \
  --visibility private
```

Use `--visibility public` only when the user explicitly requests a public upload.

## Data Use Semantics

For discovery or creator research, use `search`, `fetch`, `channel`, `playlist`, and `comments` to identify demand signals:

- recurring topics
- hook/title patterns
- viewer pain points
- format gaps
- emotional angles

Do not copy another creator's idea verbatim. Use YouTube data to derive original angles for the current project.

## Hard Rules

- Use official YouTube APIs for auth, search, metadata, comments, channels, playlists, and uploads.
- For transcript text, allow the `youtube-transcript-api` public player fallback and label it clearly.
- Do not inspect browser cookies, storage, XHR auth headers, or private Studio endpoints.
- Keep generic API commands read-only unless the command is explicitly an upload/update command.
- Do not read or write Story Video Maker `library/<project_slug>` paths from this skill.
