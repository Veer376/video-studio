# YouTube Packaging Stage

Run this optional stage only when the user requests YouTube packaging for a specific completed or near-completed `library/<project_name>` project.

## Boundaries

This skill creates:

- YouTube titles
- YouTube description with hashtags
- thumbnail image files
- thumbnail notes in `thumbnails/thumbnails.md`
- market-grounded title and thumbnail strategy in `metadata.json`

## Inputs

Read from the selected project folder:

```text
library/<project_name>/session.json
library/<project_name>/script.md
library/<project_name>/scenes.json
library/<project_name>/output/final-video.mp4
library/<project_name>/images/
```

Also read `library/<project_name>/research.md` when it exists. Packaging must remain grounded in the final script either way.

If `output/final-video.mp4` is missing, flag user.

## Output Location

Write all output under:

```text
library/<project_name>/youtube/
```

Recommended files:

```text
youtube/
└── metadata.json
```

Generate only the thumbnail images explicitly chosen by the user and save them as:

```text
youtube/
└── thumbnails/
    ├── thumbnail-01.png
    └── ... up to thumbnail-05.png
```

## Content Strategy

Create packaging for attention, but do not use fake claims. The title and thumbnail should hook curiosity, emotion, identity, or conflict without misrepresenting the story.

Optimize especially for Hindi-speaking young men and adults when the project context supports it. Use direct emotional hooks: struggle, discipline, fear, failure, faith, purpose, courage, insult, loneliness, duty, transformation, and self-respect.

Avoid generic motivational packaging. Prefer a sharp human tension from the actual script.

## Required Market Grounding

Before generating final titles or thumbnails, run a market grounding pass with the `youtube` skill. This is required for every packaging run, but it should serve the creative packaging decision rather than dominate the task.

Use the project topic, script conflict, central person/theme, and likely viewer intent to create YouTube search queries. Use the `youtube` skill's `search` and `fetch` commands to verify comparable videos before citing them.

Use the `youtube` skill's comments or transcript commands only when they can reveal viewer pain, curiosity, or language patterns.

Summarize only the useful patterns from comparable videos:

- relevance to this story
- title hook pattern
- thumbnail promise, emotion, curiosity, or pain
- title-thumbnail pairing
- what the example leaves unanswered

Do not copy title wording, thumbnail composition, scripts, or creator-specific branding. Use market examples to infer patterns, then create original packaging grounded in this project's actual story.

Market example quality gate:

- Only use comparable videos with meaningful proof of audience demand as references.
- As a hard default, a video must have at least 100,000 views before it can be included in `market_grounding.examples` or used to infer title/thumbnail strategy.
- Low-view videos are search results, not market references. Do not use videos with a few hundred or a few thousand views as examples, inspiration, or evidence.
- If the first searches do not find relevant 100k+ examples, broaden the search.
- Prefer the highest-view relevant examples, not merely the first relevant examples found.
- If no relevant 100k+ examples can be found after a serious search, stop and tell the user the market grounding did not produce strong enough examples. Do not quietly degrade to weak references.

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

1. 2-3 line emotional introduction. **The first two lines must contain primary keywords.**
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

Thumbnail generation is user-budgeted. Never assume a fixed count and never generate an image before the selection gate below.

### Concept and Count Gate

1. Create exactly **5 distinct thumbnail concepts** grounded in the chosen title strategy. Concepts are text proposals, not generated images.
2. Rank them by expected effectiveness and present all 5 with their short name, in-image text, composition, emotion, and reason.
3. Ask how many thumbnails to generate now, from **1 to 5**, using `ask_question` or an equivalent structured question tool when available. Also let the user name specific concept numbers.
4. If the user gives only a count, generate the top-ranked N concepts. If they name concepts, generate only those concepts.
5. Do not continue to image generation until the user answers. A previous generic request to "package the video" is not consent to spend image-generation credits.

Create a distinct PNG file for each selected concept only.

Each thumbnail must communicate one bold idea at a glance. Use high contrast, readable text, a clear emotional face/figure, a strong mystery cue, or a single striking visual conflict. Do not split attention across multiple competing hooks.

Reserve the bottom-right safe zone for YouTube's duration badge: keep the bottom-right 20% of width and 15% of height free of text, faces, key objects, logos, and high-contrast details. It can contain low-detail background only.

Design title and thumbnail as a pair (the Macro Loop entry point). **Title-Thumbnail Asymmetry Rule:** Title provides the context/premise (`<Hindi Hook> | <English/Hinglish Hook>`); Thumbnail MUST provide the unresolved emotional tension. NEVER repeat the title text inside the thumbnail image.

If the thumbnail uses text, the text must be hook copy, not a descriptive label. Use the same hook language as the title strategy: conflict, curiosity, reversal, stakes, insult, fear, price, secret, failure, duty, shame, self-respect, or transformation when truthful. Avoid vague fragments that do not make sense alone or give no reason to click.

Each of the 5 proposed thumbnail concepts should have a clear visual direction:

```text
Thumbnail <N>: <short name>
Visual source: generate new
In-image text: <2-5 word hook text, Hindi or Hinglish>
Composition: <clear visual layout, with bottom-right safe zone left empty>
Emotion: <viewer feeling to trigger>
Why it can work: <one concise reason>
```

Existing `images/scene-*.png` files may be inspected or used as visual references for story continuity, character look, mood, and factual details. Never use them as the thumbnail base unless the user explicitly asks.

## Thumbnail Image Generation

1. After the user passes the concept-and-count gate, generate fresh complete thumbnail images only for the selected concepts with the system `imagegen` skill or any available built-in image generation tool.
2. Include exact `In-image text` in the image generation prompt itself, integrated into the thumbnail design.
3. Use existing scene images only as optional references when useful; do not edit them into thumbnails unless the user explicitly asks.
4. Include the bottom-right safe-zone instruction in every thumbnail prompt.
5. **Mobile Quality Gate:** Verify generated thumbnails at 150px preview width to ensure high-contrast legibility of in-image text and clear facial expression visibility on mobile feeds.
6. Save final project-bound thumbnails under `library/<project_name>/youtube/thumbnails/`.
7. If no image generation capability is available, ask whether to use the project's internal image generation capability.

Do not leave thumbnail assets only in an external generated-images folder. Copy or move final selected images into the project folder.

Do not add thumbnail text later using code, PIL, Canvas, or other local overlay methods unless the user explicitly approves that fallback after image generation fails to render usable text.

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
      "visual_source": "",
      "in_image_text": "",
      "composition": "",
      "emotion": "",
      "why_it_can_work": ""
    }
  ]
}
```

## Hard Rules

- Write only inside `library/<project_name>/youtube/`.
- Run market grounding with the `youtube` skill before generating final titles or thumbnails.
- Keep packaging grounded in the actual script and research.
- Do not fabricate sources, quotes, or achievements.
- Always present 5 thumbnail concepts, then ask the user to choose a generation count from 1 to 5.
- Never generate thumbnails when the count or selected concepts are unspecified.
