# Session Config Schema

The session config is the structured output produced by the `interview-story-config` skill after completing the pre-flight questionnaire with the user. It is a JSON object written to `session.json` inside the target project folder before any content creation begins.

All downstream skills (`content-creator`, `create-story-video`) read this file to understand the creative brief for the current video.

---

## Full Schema

```json
{
  "session": {
    "created_at": "2026-07-31T18:30:00",
    "project_slug": "2026-07-31_aarav-ka-sapna",
    "status": "interview_complete"
  },
  "brief": {
    "topic": "A boy who climbs the Himalayas despite self-doubt",
    "theme": "perseverance",
    "tone": "warm storytelling",
    "language": "hi-IN",
    "audience": "general adults"
  },
  "video": {
    "target_duration_seconds": 60,
    "target_scene_count": 5,
    "seconds_per_scene": 12,
    "aspect_ratio": "16:9",
    "resolution": "1920x1080",
    "fps": 30,
    "subtitles_enabled": false
  },
  "voice": {
    "provider": "gemini_tts",
    "model": "gemini-3.1-flash-tts-preview",
    "voice": "Aoede",
    "language": "hi-IN"
  },
  "visual": {
    "style": "premium cinematic digital painting",
    "pacing": "cinematic"
  }
}
```

---

## Field Reference

### `session`
| Field | Description |
|---|---|
| `created_at` | ISO timestamp of when the interview was completed. |
| `project_slug` | Slugified folder name: `YYYY-MM-DD_<kebab-title>`. Used to create the library folder. |
| `status` | One of: `interview_complete`, `template_selected`, `script_approved`, `rendering`, `done`. |

### `brief`
| Field | Options / Notes |
|---|---|
| `topic` | Free text summary of what the story is about. |
| `theme` | Single keyword: `perseverance`, `gratitude`, `devotion`, `loss`, `hope`, `courage`, etc. |
| `tone` | `warm storytelling`, `motivational`, `educational`, `devotional`, `poetic`. |
| `language` | BCP-47 tag: `hi-IN`, `en-US`, `hi-IN+en-US` (Hinglish). |
| `audience` | `children`, `general adults`, `spiritual seekers`, `students`. |

### `video`
| Field | Notes |
|---|---|
| `target_duration_seconds` | Total final video length in seconds. |
| `target_scene_count` | Number of image/scene cuts. Derived from `target_duration_seconds / seconds_per_scene`. |
| `seconds_per_scene` | Controls pacing. Fast = 5s, Standard = 10s, Cinematic = 12-15s. |
| `aspect_ratio` | `16:9` (YouTube/horizontal) or `9:16` (Reels/Shorts). |
| `fps` | Default 30. |
| `subtitles_enabled` | `true` or `false`. |

### `voice`
| Field | Notes |
|---|---|
| `provider` | `gemini_tts` (recommended), `sarvam_tts` (Hindi-specific), `groq_tts`. |
| `model` | `gemini-3.1-flash-tts-preview` for Gemini. `bulbul:v3` for Sarvam. |
| `voice` | Gemini voices: `Aoede` (female), `Puck` (male), `Charon`, `Kore`, `Fenrir`. Sarvam: `priya`, `gokul`. |

### `visual`
| Field | Notes |
|---|---|
| `style` | Persistent style descriptor used across all image prompts in this video. |
| `pacing` | `fast` (quick cuts), `standard`, `cinematic` (slow, wide compositions). |
