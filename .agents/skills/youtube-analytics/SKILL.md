---
name: youtube-analytics
description: Standalone YouTube Analytics skill for Story Video Maker. Use when the user asks to analyze a YouTube video, fetch analytics for a library/<project_name>, inspect retention, traffic sources, countries, devices, daily performance, or run a raw YouTube Analytics report. Bundles its own youtube_analytics.py script and is not part of the main image-story pipeline.
---

# YouTube Analytics Skill

This standalone skill fetches YouTube Analytics for uploaded videos and channels.

## Boundary

Use the bundled script only:

```bash
python3 .agents/skills/youtube-analytics/scripts/youtube_analytics.py fetch library/<project_name>
python3 .agents/skills/youtube-analytics/scripts/youtube_analytics.py video <video_id_or_url>
python3 .agents/skills/youtube-analytics/scripts/youtube_analytics.py channel
python3 .agents/skills/youtube-analytics/scripts/youtube_analytics.py query --metrics views
```

The script manages OAuth automatically.

## Project Input

For project analytics, read:

```text
library/<project_name>/youtube/upload.json
```

The file must contain `video_id`.

## Project Output

Project fetches write:

```text
library/<project_name>/youtube/analytics.json
```

Do not create Markdown reports or cache files.

## Commands

Fetch analytics for one project:

```bash
python3 .agents/skills/youtube-analytics/scripts/youtube_analytics.py fetch library/<project_name>
```

Fetch analytics for a video URL or ID without writing project files:

```bash
python3 .agents/skills/youtube-analytics/scripts/youtube_analytics.py video <video_id_or_url>
```

Attach analytics for a video URL or ID to a project:

```bash
python3 .agents/skills/youtube-analytics/scripts/youtube_analytics.py video <video_id_or_url> --project library/<project_name>
```

Fetch channel-level analytics:

```bash
python3 .agents/skills/youtube-analytics/scripts/youtube_analytics.py channel
```

Run a raw report:

```bash
python3 .agents/skills/youtube-analytics/scripts/youtube_analytics.py query \
  --metrics views,estimatedMinutesWatched \
  --dimensions day \
  --filters video==<video_id>
```

## Default Reports

For project/video fetches, collect:

- overview metrics
- daily performance
- audience retention curve
- traffic sources
- countries
- device types

Some reports may return no rows for new videos or low-data videos. Preserve the successful reports and record per-report errors instead of failing the whole fetch.

## Hard Rules

- Use only official YouTube Analytics API calls.
- Do not inspect browser cookies, storage, XHR auth headers, or private Studio endpoints.
- Do not modify project files except `library/<project_name>/youtube/analytics.json`.
- Do not create list cache files.
- Do not invent analytics. If YouTube has no rows yet, report no data.
