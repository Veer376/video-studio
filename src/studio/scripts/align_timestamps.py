"""
Align Groq word timestamps to scenes using word_range indices.
Updates scenes.json in-place with start_time and end_time per scene.

Usage:
    python3 align_timestamps.py --project-dir library/2026-08-01_krishna-motivation
"""
import argparse
import json
import sys
from pathlib import Path


def align_direct(scenes: list, words: list, duration: float) -> list:
    """
    Direct index mapping: scene.word_range[0] → words[i].start
    Used when Groq word count is within 15% of storyboard word count.
    """
    for scene in scenes:
        start_idx, end_idx = scene["word_range"]
        # Clamp to valid range
        start_idx = max(0, min(start_idx, len(words) - 1))
        end_idx = max(0, min(end_idx, len(words) - 1))

        scene["start_time"] = round(float(words[start_idx]["start"]), 3)
        scene["end_time"] = round(float(words[end_idx]["end"]), 3)
    return scenes


def align_scaled(scenes: list, words: list, total_storyboard_words: int) -> list:
    """
    Map storyboard word indices onto Whisper word indices proportionally.
    Used when counts are close enough to trust order, but not identical.
    """
    storyboard_last = max(total_storyboard_words - 1, 1)
    whisper_last = max(len(words) - 1, 0)

    for scene in scenes:
        start_idx, end_idx = scene["word_range"]
        start_idx = max(0, min(start_idx, storyboard_last))
        end_idx = max(0, min(end_idx, storyboard_last))

        mapped_start = round((start_idx / storyboard_last) * whisper_last)
        mapped_end = round((end_idx / storyboard_last) * whisper_last)
        mapped_start = max(0, min(mapped_start, whisper_last))
        mapped_end = max(mapped_start, min(mapped_end, whisper_last))

        scene["start_time"] = round(float(words[mapped_start]["start"]), 3)
        scene["end_time"] = round(float(words[mapped_end]["end"]), 3)
    return scenes


def align_proportional(scenes: list, total_storyboard_words: int, duration: float) -> list:
    """
    Fallback: map word indices proportionally to audio duration.
    Used when Groq word count significantly mismatches storyboard word count.
    """
    print("  ⚠ Word count mismatch — using proportional time mapping as fallback.", file=sys.stderr)
    for scene in scenes:
        start_idx, end_idx = scene["word_range"]
        scene["start_time"] = round((start_idx / total_storyboard_words) * duration, 3)
        scene["end_time"] = round(((end_idx + 1) / total_storyboard_words) * duration, 3)
    return scenes


def normalize_scene_intervals(scenes: list, duration: float) -> list:
    """
    Render uses scene start/end as visual clip intervals. Make those intervals
    continuous so pauses and trailing audio are not dropped from the final video.
    """
    if not scenes:
        return scenes

    starts = [float(scene.get("start_time") or 0.0) for scene in scenes]
    starts[0] = 0.0

    for idx in range(1, len(starts)):
        minimum_start = starts[idx - 1] + 0.1
        starts[idx] = max(starts[idx], minimum_start)
        starts[idx] = min(starts[idx], max(duration - 0.1, minimum_start))

    for idx, scene in enumerate(scenes):
        scene["start_time"] = round(starts[idx], 3)
        if idx < len(scenes) - 1:
            scene["end_time"] = round(starts[idx + 1], 3)
        else:
            scene["end_time"] = round(duration, 3)

    return scenes


def main():
    parser = argparse.ArgumentParser(description="Align Groq timestamps to scene word ranges")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory")
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    scenes_path = project_dir / "scenes.json"
    timestamps_path = project_dir / "audio" / "timestamps.json"

    if not scenes_path.exists():
        print(f"ERROR: scenes.json not found at {scenes_path}", file=sys.stderr)
        sys.exit(1)
    if not timestamps_path.exists():
        print(f"ERROR: timestamps.json not found at {timestamps_path}", file=sys.stderr)
        sys.exit(1)

    scenes_data = json.loads(scenes_path.read_text(encoding="utf-8"))
    ts_data = json.loads(timestamps_path.read_text(encoding="utf-8"))

    scenes = scenes_data["scenes"]
    words = ts_data["words"]
    duration = float(ts_data["duration"])
    groq_word_count = len(words)

    # Derive total storyboard words from the last scene's word_range
    last_end_idx = scenes[-1]["word_range"][1]
    total_storyboard_words = last_end_idx + 1

    print(f"→ Aligning {len(scenes)} scenes")
    print(f"  Storyboard words: {total_storyboard_words} | Groq words: {groq_word_count} | Duration: {duration:.2f}s")

    mismatch_ratio = abs(groq_word_count - total_storyboard_words) / max(total_storyboard_words, 1)

    if mismatch_ratio == 0:
        print("  Using direct index alignment (word counts within 15% tolerance)")
        scenes = align_direct(scenes, words, duration)
    elif mismatch_ratio <= 0.15:
        print("  Using scaled index alignment (word counts close but not identical)")
        scenes = align_scaled(scenes, words, total_storyboard_words)
    else:
        scenes = align_proportional(scenes, total_storyboard_words, duration)

    scenes = normalize_scene_intervals(scenes, duration)
    scenes_data["scenes"] = scenes

    # Write updated scenes.json
    scenes_path.write_text(json.dumps(scenes_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"✓ scenes.json updated with timestamps")
    print(f"  First scene: {scenes[0]['start_time']}s → {scenes[0]['end_time']}s")
    print(f"  Last scene:  {scenes[-1]['start_time']}s → {scenes[-1]['end_time']}s")


if __name__ == "__main__":
    main()
