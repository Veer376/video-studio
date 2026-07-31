# Story Manifest Schema (`story.json`)

The `story.json` manifest coordinates the entire story rendering pipeline, including project specifications, voice synthesis configurations, character definitions, visual style constraints, and individual scene components.

Below is the structure of the JSON manifest, which maps to the Python dataclasses defined in `src/story_video/models.py`.

## Top-Level Fields

- `project` (Object, required): Global project settings (aspect ratio, resolution, fps, etc.).
- `characters` (Array, required): List of character description objects used to maintain visual and narrative continuity.
- `visual_style` (Object, required): Specifications for image generation style, color palettes, and rendering constraints.
- `voice` (Object, required): Settings for TTS generation (provider, voices, speed, models, transport mechanism).
- `scenes` (Array, required): Detailed scene-by-scene instructions and asset paths.
- `background_music_path` (String, optional): Absolute or project-relative path to background audio.
- `subtitles_enabled` (Boolean, optional): Whether to burn subtitles onto the final video. Default is `false`.
- `target_scene_count` (Integer, optional): Intended number of scenes in the video.
- `target_duration_seconds` (Integer, optional): Goal duration in seconds for the entire output.

---

## Component Details

### `project`
- `title` (string): Title of the story.
- `language` (string): BCP-47 language tag (e.g., `"hi-IN"`, `"en-US"`).
- `aspect_ratio` (string): Desired aspect ratio (e.g., `"16:9"`, `"9:16"`).
- `resolution` (string): Resolution as `"{width}x{height}"` (e.g., `"1920x1080"`).
- `fps` (integer): Frame rate (e.g., `30`).

### `voice`
- `provider` (string): TTS provider name (e.g., `"gemini_tts"`, `"sarvam_tts"`, `"groq_tts"`, `"existing_audio"`).
- `voice` (string, optional): Default voice ID/name.
- `male_voice` (string, optional): Voice ID to use for male-narrated tracks.
- `female_voice` (string, optional): Voice ID to use for female-narrated tracks.
- `instructions` (string, optional): Prompt details or notes for narration tone/pacing.
- `model` (string, optional): Specific TTS model name (e.g., `"bulbul:v3"`).
- `response_format` (string, default `"wav"`): Audio format.
- `sample_rate` (integer, optional): Desired audio sample rate.
- `speed` (float, optional): Speed modifier factor.
- `transport` (string, optional): API connection option (e.g., `"rest_stream"`).

### `scenes` (Array of Scene Objects)
Each scene in the `scenes` list represents a video segment containing:
- `id` (string): Unique identifier (e.g., `"scene-001"`).
- `narration` (string): Voiceover script text.
- `voice_direction` (string): Guidance on tone or delivery of the narration.
- `image_prompt` (string): Detailed image generator prompt.
- `reference_images` (array of strings): Input reference images for image generators.
- `image_path` (string | null): Path to the generated/collected image file (e.g., `"generated/images/scene-001.png"`).
- `audio_path` (string | null): Path to the paced voice file (e.g., `"generated/audio/paced/scene-001.wav"`).
- `duration_seconds` (float | null): Measured duration of the paced audio segment.
- `subtitle` (string): Burned-in subtitle text for the scene.
- `motion` (Object):
  - `type` (string): Motion effect (e.g., `"slow_zoom_in"`, `"slow_zoom_out"`, `"slow_pan_right"`, `"slow_pan_left"`).
  - `intensity` (float): Motion speed/magnitude.
- `transition` (Object):
  - `type` (string): Transition style (e.g., `"crossfade"`).
  - `duration_seconds` (float): Length of the transition in seconds.
- `errors` (array of strings): Pipeline validation error messages.
