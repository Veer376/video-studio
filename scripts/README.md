# Scripts

This directory contains durable, reusable project pipeline and media utilities. Every script must remain useful beyond the task that introduced it.

## Standards

1. **Executable & Shebang**:
   - Begin every script with `#!/usr/bin/env python3`.
   - Ensure files have executable permissions (`chmod +x`).

2. **Story-Agnostic Design**:
   - Never hardcode project paths, scene IDs, or project-specific assets.
   - Expose configurable parameters via CLI arguments (e.g. `--config`, `--story`, `--input`, `--output`).

3. **Standard CLI Interface**:
   - Use `argparse` with clear `--help` descriptions and sensible defaults.
   - Use `Path(__file__).resolve().parent.parent` for workspace-relative path resolution so scripts run reliably from any working directory.

4. **Directory Ownership**:
   - `scripts/`: Backend pipeline tools, video processing, and media automation utilities.
   - `app/`: Interactive Terminal UI (TUI) and desktop GUI applications.
   - `scratch/` & `temp/`: Ad-hoc experiments, scraping tests, and transient artifacts.

---

## Media Utilities Reference

| Script | Purpose | Key Flags | Example |
|---|---|---|---|
| `project.py` | Create the canonical files and directories for a new video project | `create`, `--title`, `--aspect-ratio`, `--slug` | `python3 scripts/project.py create --title "Flying Auto" --aspect-ratio 9:16` |
| `generate_scenes.py` | Generate an active scene video or restore an archived version | `--config`, `--scene`, `--regenerate`, `--restore` | `python3 scripts/generate_scenes.py --config projects/project/scenes.json --scene s001` |
| `extract_frame.py` | Extract pristine first, last, or timestamp frame from a video | `-i`, `-o`, `-p {last,first,timestamp}`, `-t <secs>` | `python3 scripts/extract_frame.py -i clip.mp4 -p last -o last_frame.png` |
| `concat_videos.py` | Seamlessly concatenate multiple MP4 videos in sequence | `-i <file1> <file2> ...`, `-o <merged.mp4>` | `python3 scripts/concat_videos.py -i s01.mp4 s02.mp4 -o full.mp4` |
| `render_video.py` | Assemble accepted active scenes from `scenes.json` | `--config <path>`, `--output <path>`, `--watermark-image <path>` | `python3 scripts/render_video.py --config projects/project/scenes.json` |
| `apply_watermark.py`| Apply channel watermark to video | `--input`, `--output`, `--image` | `python3 scripts/apply_watermark.py -i raw.mp4 -o wm.mp4` |
| `cut_video.py` | Cut out sections or extract windows with safe in-place replace | `-i`, `-o`, `--cut-start`, `--cut-end`, `--cut`, `--keep`, `--backup` | `cut-video -i clip.mp4 --cut-start 2.5 --backup` |
| `render_text.py` | Render text overlays and captions | `--input`, `--output`, `--text` | `python3 scripts/render_text.py` |
| `add_loop.py` | Create seamless loops for clips | `--input`, `--output` | `python3 scripts/add_loop.py` |
| `add_background_music.py` | Mix music beneath dialogue with smooth sidechain ducking | `--input`, `--music`, `--output`, `--music-volume-db` | `python3 scripts/add_background_music.py -i final.mp4 -m score.m4a -o final-with-music.mp4` |
