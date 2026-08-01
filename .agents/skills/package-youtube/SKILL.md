---
name: package-youtube
description: Standalone YouTube packaging skill for Story Video Maker. Use when the user asks to create YouTube-ready title, description, tags, script-in-description, or thumbnails for an existing library/<project_slug> video. Writes packaging files under the project slug's youtube/ folder only; does not participate in the main image-story creation pipeline.
---

# Package YouTube Skill

This skill packages a completed or near-completed Story Video Maker project for YouTube. It is not part of the main creation flow and should only run when the user asks for YouTube upload content for a specific `library/<project_slug>`.

## Boundaries

This skill may create:

- YouTube titles
- YouTube description
- hashtag block inside the YouTube description
- thumbnail image files
- thumbnail notes in `thumbnails/thumbnails.md`

This skill must not:

- modify `session.json`
- rewrite `script.md`
- edit `scenes.json`
- run `run-pipeline`
- link itself into `create-image-story` resume logic
- change the final video

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

If `output/final-video.mp4` is missing, continue only if the user explicitly wants packaging before final render.

## Output Location

Write all output under:

```text
library/<project_slug>/youtube/
```

Recommended files:

```text
youtube/
├── metadata.md
└── metadata.json
```

Always generate actual thumbnail images and save them as:

```text
youtube/
└── thumbnails/
    ├── thumbnail-01.png
    ├── thumbnail-02.png
    ├── thumbnail-03.png
    └── thumbnails.md
```

Use `thumbnails/thumbnails.md` only to explain the generated thumbnail variants, including source image, overlay text, composition, and why each variant may work. Do not create per-thumbnail Markdown files.

## Content Strategy

Create packaging for attention, but do not use fake claims. The title and thumbnail should hook curiosity, emotion, identity, or conflict without misrepresenting the story.

Optimize especially for Hindi-speaking young men and adults when the project context supports it. Use direct emotional hooks: struggle, discipline, fear, failure, faith, purpose, courage, insult, loneliness, duty, transformation, and self-respect.

Avoid generic motivational packaging. Prefer a sharp human tension from the actual script.

## Title Rules

Create 5 title options.

Each title must use:

```text
<Hindi hook> | <English hook>
```

Rules:

- Hindi side should carry the emotion.
- English side should make the topic searchable.
- Keep each title short enough for YouTube scanning.
- Do not stuff keywords.

## Description Rules

Write one final description with:

1. 2-3 line emotional introduction.
2. Short promise of what the viewer will understand.
3. Optional quote/source note only if it naturally belongs.
4. Full cleaned script or narration transcript.
5. A copy-paste-ready hashtag block.

The description should feel human, not SEO-generated.

## Hashtag Block

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
- emotional theme tags
- audience intent tags

## Thumbnail Images

Create 3 distinct thumbnail PNG files for every YouTube packaging run.

Each thumbnail must communicate one bold idea at a glance. Use high contrast, readable text, a clear emotional face/figure, a strong mystery cue, or a single striking visual conflict. Do not split attention across multiple competing hooks.

Reserve the bottom-right safe zone for YouTube's duration badge: keep the bottom-right 20% of width and 15% of height free of text, faces, key objects, logos, and high-contrast details. It can contain low-detail background only.

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

Record the final thumbnail variant notes in `youtube/thumbnails/thumbnails.md` after generating images. Keep these notes concise and tied to the actual PNG files created.

## Thumbnail Image Generation

1. Prefer the system `imagegen` skill or any available built-in image generation tool.
2. Use existing scene images as references when useful.
3. Include the bottom-right safe-zone instruction in every thumbnail prompt.
4. Save final project-bound thumbnails under `library/<project_slug>/youtube/thumbnails/`.
5. If no image generation capability is available, ask whether to use the project's internal image generation capability.

Do not leave thumbnail assets only in an external generated-images folder. Copy or move final selected images into the project folder.

## `metadata.md` Shape

```markdown
# YouTube Package: <project title>

## Recommended Title
<Hindi hook> | <English hook>

## Alternate Titles
1. <...>
2. <...>
3. <...>
4. <...>

## Description
<final upload description>
```

## `metadata.json` Shape

```json
{
  "recommended_title": "",
  "alternate_titles": [],
  "description": ""
}
```

## Hard Rules

- Write only inside `library/<project_slug>/youtube/`.
- Keep packaging grounded in the actual script and research.
- Do not fabricate sources, quotes, or achievements.
- Do not force a quote if the story does not need one.
- Do not output separate tags; include all tags as hashtags inside the description.
- Always generate 3 thumbnail PNGs and `youtube/thumbnails/thumbnails.md`.
