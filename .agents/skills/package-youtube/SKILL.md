---
name: package-youtube
description: YouTube packaging skill for Story Video Maker. Use when the user asks to create YouTube-ready title, description, tags, script-in-description, or thumbnails for an existing library/<project_slug> video. Writes packaging files under the project slug's youtube/ folder only; does not participate in the main image-story creation pipeline.
---

# Package YouTube Skill

This skill packages a completed or near-completed Story Video Maker project for YouTube. It is not part of the main creation flow and should only run when the user asks for YouTube upload content for a specific `library/<project_slug>`.

## Boundaries

This skill may create:

- YouTube titles
- YouTube description with hashtags
- thumbnail image files
- thumbnail notes in `thumbnails/thumbnails.md`
- market-grounded title and thumbnail strategy in `metadata.json`

This skill must not:

- modify `session.json`, `script.md`, `scenes.json`
- run `run-pipeline` 

## Inputs

Read from the selected project folder:

```text
library/<project_slug>/session.json
library/<project_slug>/research.md
library/<project_slug>/script.md
library/<project_slug>/scenes.json
library/<project_slug>/output/final-video.mp4
library/<project_slug>/images/
```

If `output/final-video.mp4` is missing, flag user.

## Output Location

Write all output under:

```text
library/<project_slug>/youtube/
```

Recommended files:

```text
youtube/
└── metadata.json
```

Always generate actual thumbnail images and save them as:

```text
youtube/
└── thumbnails/
    ├── thumbnail-01.png
    ├── thumbnail-02.png
    └── thumbnail-03.png
```

## Content Strategy

Create packaging for attention, but do not use fake claims. The title and thumbnail should hook curiosity, emotion, identity, or conflict without misrepresenting the story.

Optimize especially for Hindi-speaking young men and adults when the project context supports it. Use direct emotional hooks: struggle, discipline, fear, failure, faith, purpose, courage, insult, loneliness, duty, transformation, and self-respect.

Avoid generic motivational packaging. Prefer a sharp human tension from the actual script.

## Required Market Grounding

Before generating final titles or thumbnails, run a market grounding pass with the `youtube` skill. This is required for every packaging run.

Use the project topic, script conflict, central person/theme, and likely viewer intent to create 3-5 YouTube search queries. Then use:

```bash
python3 .agents/skills/youtube/scripts/youtube.py search "<query>" --max-results 10
python3 .agents/skills/youtube/scripts/youtube.py fetch <video_id_or_url>
```

Use comments or transcripts only when they can reveal viewer pain, curiosity, or language patterns:

```bash
python3 .agents/skills/youtube/scripts/youtube.py comments <video_id_or_url> --max-results 20
python3 .agents/skills/youtube/scripts/youtube.py transcript <video_id_or_url> --language hi
```

Evaluate comparable videos by:

- relevance to this story
- views per day, not raw views alone
- title hook pattern
- thumbnail promise, emotion, curiosity, or pain
- title-thumbnail pairing
- what the example leaves unanswered

Do not copy title wording, thumbnail composition, scripts, or creator-specific branding. Use market examples to infer patterns, then create original packaging grounded in this project's actual story.

If YouTube API access fails, stop and tell the user the market grounding step could not run. **Do not silently fall back to ungrounded packaging.**

## Title Rules

Create 5 title options.

Each title must use:

```text
<Hindi hook> | <Hindlish hook> or <English hook>
```

Rules:

- Hindi side should carry the emotion.
- English side words should be commonly used in Indian Hindi speech - terms the viewer already thinks in (fail, struggle, PG, boss, tension). The goal is recognition and reach.
- Keep each title short enough for YouTube scanning.
- Do not stuff keywords.
- Derive final title strategy from the required market grounding pass.
- Avoid copying market examples; adapt only the observed hook pattern.

## Description Rules

Write one final description with:

1. 2-3 line emotional introduction.
2. Short promise of what the viewer will understand.
3. Optional quote/source note only if it naturally belongs.
4. Full cleaned script or narration transcript.
5. A copy-paste-ready hashtags in the end.

The description should feel human, not SEO-generated.

## Hashtags

Create 20-30 hashtag-style tags and place them at the end of the description itself.

Rules:

- Do not create a separate `Tags` section.
- Do not create comma-separated non-hashtag tags.
- Every tag must start with `#`.
- Remove spaces and punctuation inside hashtag terms so they are directly pasteable.

Mix:

- topic/person tags
- Hindi search tags
- English search tags
- Hindlish search tags
- emotional theme tags
- audience intent tags

## Thumbnail Images

Create 3 distinct thumbnail PNG files for every YouTube packaging run.

Each thumbnail must communicate one bold idea at a glance. Use high contrast, readable text, a clear emotional face/figure, a strong mystery cue, or a single striking visual conflict. Do not split attention across multiple competing hooks.

Reserve the bottom-right safe zone for YouTube's duration badge: keep the bottom-right 20% of width and 15% of height free of text, faces, key objects, logos, and high-contrast details. It can contain low-detail background only.

Design title and thumbnail as a pair. The thumbnail should not merely repeat the title; it should create the unresolved emotional moment that makes the title more clickable.

Each generated thumbnail should have a clear visual direction:

```text
Thumbnail <N>: <short name>
Base image: <scene image path or "generate new">
Overlay text: <2-4 words, Hindi preferred>
Composition: <clear visual layout, with bottom-right safe zone left empty>
Emotion: <viewer feeling to trigger>
Why it can work: <one concise reason>
```

Prefer using an existing strong scene image from `images/` as the base. Generate a new thumbnail background only when existing scene images cannot carry the hook.

## Thumbnail Image Generation

1. Prefer the system `imagegen` skill or any available built-in image generation tool.
2. Use existing scene images as references when useful.
3. Include the bottom-right safe-zone instruction in every thumbnail prompt.
4. Save final project-bound thumbnails under `library/<project_slug>/youtube/thumbnails/`.
5. If no image generation capability is available, ask whether to use the project's internal image generation capability.

Do not leave thumbnail assets only in an external generated-images folder. Copy or move final selected images into the project folder.

## `metadata.json` Shape

```json
{
  "recommended_title": "",
  "alternate_titles": [],
  "description": "",
  "market_grounding": {
    "queries": [],
    "examples": [
      {
        "video_id": "",
        "url": "",
        "title": "",
        "channel": "",
        "published_at": "",
        "views": 0,
        "views_per_day": 0,
        "thumbnail_url": "",
        "relevance": "",
        "observed_hook": "",
        "thumbnail_pattern": "",
        "takeaway": ""
      }
    ],
    "title_patterns": [],
    "thumbnail_patterns": [],
    "rejected_patterns": [],
    "chosen_title_strategy": "",
    "chosen_thumbnail_strategy": ""
  },
  "thumbnails": [
    {
      "file": "thumbnails/thumbnail-01.png",
      "name": "",
      "base_image": "",
      "overlay_text": "",
      "composition": "",
      "emotion": "",
      "why_it_can_work": ""
    }
  ]
}
```

## Hard Rules

- Write only inside `library/<project_slug>/youtube/`.
- Run market grounding with the `youtube` skill before generating final titles or thumbnails.
- Keep packaging grounded in the actual script and research.
- Do not fabricate sources, quotes, or achievements.
- Always generate 3 thumbnail PNGs.