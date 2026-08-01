---
name: voice
description: Audio generation and timestamp extraction skill. Generates a single full narration audio from script.md using Gemini TTS, then passes it to Groq Whisper for word-level timestamps. Also aligns those timestamps to the scenes in scenes.json. Runs after storyboard.
---

# Voice Skill

This skill generates all audio assets and timestamps for the pipeline. It has three steps, each backed by an executable script.

---

## When to Activate

Activate this skill when:
- `session.json` exists with `status: "storyboard_complete"`
- `script.md` and `scenes.json` both exist

---

## Overview

The voice skill transforms `script.md` into three outputs:

```
script.md
    ↓ generate_audio.py
audio/narration.wav          ← single, full, natural narration
    ↓ extract_timestamps.py
audio/timestamps.json        ← word-by-word Groq Whisper output
    ↓ align_timestamps.py
scenes.json (updated)        ← start_time + end_time filled per scene
```

---

## Step 1 — Generate Full Audio

**Script:** `.agents/skills/voice/scripts/generate_audio.py`

This script reads `script.md`, extracts the pure narration body (everything after the `---` separator), and calls Gemini TTS to generate a single continuous WAV file.

```bash
python3 .agents/skills/voice/scripts/generate_audio.py \
  --project-dir library/<project_slug>
```

**What it does:**
- Reads `library/<project_slug>/session.json` for `voice.model` and `voice.voice`
- Reads `library/<project_slug>/script.md` and strips the metadata header (title, template, date, description — everything before `---`)
- Calls Gemini TTS via REST API (same pattern as existing `src/audio/gemini.py`)
- Writes WAV to `library/<project_slug>/audio/narration.wav`
  - Format: PCM 16-bit, 24000 Hz, mono (Gemini's native output)

---

## Step 2 — Extract Word Timestamps

**Script:** `.agents/skills/voice/scripts/extract_timestamps.py`

This script sends `narration.wav` to Groq Whisper and saves the word-level timestamp output.

```bash
python3 .agents/skills/voice/scripts/extract_timestamps.py \
  --project-dir library/<project_slug>
```

**What it does:**
- Reads `library/<project_slug>/audio/narration.wav`
- Calls Groq Whisper API (`whisper-large-v3`) with:
  - `response_format: "verbose_json"`
  - `timestamp_granularities: ["word"]`
  - `language: "hi"`
- Saves the full word-list to `library/<project_slug>/audio/timestamps.json`

**`timestamps.json` schema:**
```json
{
  "duration": 240.5,
  "language": "hi",
  "word_count": 847,
  "words": [
    {"word": "क्या",  "start": 0.12, "end": 0.45},
    {"word": "आप",    "start": 0.47, "end": 0.65},
    {"word": "जानते", "start": 0.68, "end": 1.10}
  ]
}
```

> [!NOTE]
> `word.start` and `word.end` are floats in seconds. All downstream scripts
> treat them as floats — never cast to int.

---

## Step 3 — Align Timestamps to Scenes

**Script:** `.agents/skills/voice/scripts/align_timestamps.py`

This script reads `scenes.json` (which has `word_range` per scene) and `timestamps.json` (which has per-word timing), and uses the word indices to fill in `start_time` / `end_time` for every scene in `scenes.json`.

```bash
python3 .agents/skills/voice/scripts/align_timestamps.py \
  --project-dir library/<project_slug>
```

**How alignment works:**
```
scene.word_range = [0, 42]
scene.start_time = timestamps.words[0].start   → 0.12
scene.end_time   = timestamps.words[42].end    → 13.84
```

**Mismatch handling:**
Groq may return a slightly different word count than the script due to Hindi tokenization. The aligner handles this:
- If Groq word count is within 15% of script word count → direct index mapping
- Otherwise → proportional time mapping (fallback):
  `start_time = (scene.word_range[0] / total_groq_words) * duration`

After alignment, `scenes.json` is updated in-place. Every scene will have non-null `start_time` and `end_time`.

---

## Output File Summary

| File | Format | Content |
|---|---|---|
| `audio/narration.wav` | WAV, 24000 Hz, 16-bit, mono | Full narration audio |
| `audio/timestamps.json` | JSON | Groq word timestamps (raw) |
| `scenes.json` | JSON (updated) | `start_time` + `end_time` filled |

---

## Update Status

After all three steps complete successfully, update `session.json`:
- Set `session.status` to `"voice_complete"`

---

## Hard Rules

- **One audio file only.** Never generate per-scene audio. The whole pipeline depends on a single continuous audio track.
- **Never cast timestamps to int.** `start_time` and `end_time` must always be stored as floats.
- **Do not alter `word_range` in scenes.json** — that is set by the storyboard skill and is immutable.
- **narration.wav must be stripped of all metadata text** before sending to TTS. No headers, no template names, no dates — only the spoken narration prose.
