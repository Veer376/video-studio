---
name: illustrate
description: Image generation skill. Reads the scenes.json and calls Cloudflare Workers AI flux-1-schnell model to generate scene-specific images. Handles aspect ratio mapping, key loading, and updates image_path in scenes.json. Runs after voice.
---

# Illustrate Skill

This skill is a **lead illustrator**. It reads the storyboard in `scenes.json` and generates the corresponding visual assets using Cloudflare Workers AI `flux-1-schnell` model.

---

## When to Activate

Activate this skill when:
- `scenes.json` exists with timing information filled (status in `session.json` is `"voice_complete"`)
- `image_path` in `scenes.json` is `null` (or images are missing)

---

## Aspect Ratio & Resolution Mapping

Do **not** generate generic square images unless requested. The script reads `session.json` `video.aspect_ratio` and maps it to the exact width and height dimensions supported by Flux:

| Aspect Ratio | Dimensions | Use Case |
|---|---|---|
| **`16:9`** | `width: 1024`, `height: 576` | YouTube Landscape |
| **`9:16`** | `width: 576`, `height: 1024` | Reels / Shorts Vertical |
| **`1:1`** | `width: 768`, `height: 768` | Instagram Post / Square |

---

## Execution Command

Run the custom script to generate all images:

```bash
python3 .agents/skills/illustrate/scripts/generate_images.py \
  --project-dir library/<project_slug>
```

**Options:**
- `--force`: Regenerate all images even if they already exist on disk.
- `--concurrency N`: Number of concurrent workers (default is `3` to avoid rate limits).

---

## Workflow Details

The CLI script executes these steps:

1. **Load Keys:** Reads `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` from `~/.config/story-video-maker/.env`.
2. **Read Config & Manifest:** Loads `session.json` and `scenes.json` from the project directory.
3. **Determine Resolution:** Standardizes width/height based on aspect ratio config.
4. **Iterate Scenes:** For each scene in `scenes.json`:
   - Combine the global style and local prompt:
     `full_prompt = f"{visual_style} — {scene.image_prompt}"`
   - Send a POST request to:
     `https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell`
   - Save the returned binary image data directly to `library/<project_slug>/images/{scene_id}.png`.
   - Update `scene.image_path` to `images/{scene_id}.png`.
5. **Update Manifest:** Write the updated `scenes.json` to disk in-place.
6. **Update Status:** Change `session.status` in `session.json` to `"illustrate_complete"`.

---

## Hard Rules

- **Prepend Visual Style:** The final image prompt sent to Cloudflare must always prefix the scene's prompt with the global visual style (e.g. `visual_style — scene_prompt`).
- **Respect Aspect Ratio:** Always generate landscape (`1024x576`) for `16:9` aspect ratios to avoid boxy borders.
- **WAV/Audio is untouched:** Only generate images and update paths.
