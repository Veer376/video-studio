"""
Stage 1 of render pipeline: Generate ASS subtitle file from Groq word timestamps.

Each word from Groq timestamps is mapped to its scene via start_time/end_time boundaries.
Within each scene, subtitles build cumulatively (karaoke style) — each new word reveals
the text so far, timed exactly to the spoken word.

Usage:
    python3 render_subtitles.py --project-dir library/2026-08-01_krishna-motivation
"""
import argparse
import json
import sys
from pathlib import Path

RENDER_WIDTH = 1920
RENDER_HEIGHT = 1080


def format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format H:MM:SS.cs (centiseconds)."""
    cs = round(seconds * 100)
    h = cs // 360000
    cs %= 360000
    m = cs // 6000
    cs %= 6000
    s = cs // 100
    cs %= 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def detect_devanagari_font(base_dir: Path) -> tuple[str, Path | None]:
    """
    Detect an installed Devanagari-compatible font.
    Returns (font_name, font_dir) — font_dir is used as fontsdir in FFmpeg ass filter.
    """
    candidates = [
        ("/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc", "Devanagari Sangam MN"),
        ("/System/Library/Fonts/Supplemental/ITFDevanagari.ttc", "ITF Devanagari"),
        ("/System/Library/Fonts/Supplemental/DevanagariMT.ttc", "Devanagari MT"),
        ("/System/Library/Fonts/Supplemental/Noto Sans Devanagari.ttc", "Noto Sans Devanagari"),
        ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf", "Noto Sans Devanagari"),
    ]
    # Check project-local fonts first
    local_font = base_dir / "assets/fonts/Devanagari.ttf"
    if local_font.exists():
        return ("Devanagari", local_font.parent)

    for path_str, name in candidates:
        p = Path(path_str)
        if p.exists():
            return (name, p.parent)

    # Fallback — Arial can handle some Devanagari
    return ("Arial", None)


def assign_words_to_scenes(words: list[dict], scenes: list[dict]) -> dict[int, list[dict]]:
    """
    Assign each Groq word to exactly one scene using a greedy single-pass assignment.
    Each word is assigned to the first scene (by scene order) whose [start_t, end_t) window
    contains the word's start time. Returns dict mapping scene index -> list of assigned words.
    Guarantees zero word duplication across adjacent scenes.
    """
    scene_windows = []
    for idx, scene in enumerate(scenes):
        start_t = scene.get("start_time")
        end_t = scene.get("end_time")
        if start_t is not None and end_t is not None:
            scene_windows.append((float(start_t), float(end_t), idx))
    scene_windows.sort(key=lambda x: x[0])

    assignment: dict[int, list[dict]] = {i: [] for i in range(len(scenes))}
    scene_idx = 0
    m = len(scene_windows)

    if m == 0:
        return assignment

    for word in words:
        w_start = float(word["start"])
        while scene_idx < m - 1 and w_start >= scene_windows[scene_idx][1]:
            scene_idx += 1
        start_t, end_t, real_idx = scene_windows[scene_idx]
        if w_start >= start_t and w_start < end_t:
            assignment[real_idx].append(word)

    return assignment


def write_ass_file(
    scenes: list[dict],
    words: list[dict],
    out_path: Path,
    width: int = 1080,
    height: int = 1920,
    font_name: str = "Arial",
    font_size: int = 40,
    margin_v: int = 200,
    outline: int = 4,
    shadow: int = 2,
) -> Path:
    """
    Generate an ASS subtitle file from scene windows and Groq word timestamps.
    """
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
Collisions: Normal
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,20,20,{margin_v},0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogue_lines: list[str] = []
    word_assignments = assign_words_to_scenes(words, scenes)

    for idx, scene in enumerate(scenes):
        start_t = scene.get("start_time")
        end_t = scene.get("end_time")
        if start_t is None or end_t is None:
            continue

        # Collect Groq words assigned strictly to this scene (zero duplication)
        scene_words = word_assignments.get(idx, [])
        if not scene_words:
            # Fallback Protection: Do not drop subtitles. Render static scene text over scene duration.
            raw_text = scene.get("text", "").replace(">", "").strip()
            safe_text = raw_text.replace("{", "").replace("}", "")
            if safe_text:
                dialogue_lines.append(
                    f"Dialogue: 0,{format_ass_time(float(start_t))},{format_ass_time(float(end_t))},"
                    f"Default,,0,0,0,,{safe_text}"
                )
            continue

        # Build cumulative word-reveal entries
        cumulative: list[str] = []
        for i, word in enumerate(scene_words):
            clean_word = word["word"].replace(">", "").strip()
            if clean_word:
                cumulative.append(clean_word)
            display_text = " ".join(cumulative)

            t_start = float(word["start"])
            # End exactly when the next word starts, or at scene end for last word
            if i < len(scene_words) - 1:
                t_end = float(scene_words[i + 1]["start"])
            else:
                t_end = float(end_t)

            # Skip zero or negative duration entries (can happen at boundary edges)
            if t_end <= t_start + 0.001:
                continue

            # ASS escape: { and } are special in ASS; replace curly braces if any
            safe_text = display_text.replace("{", "").replace("}", "")

            dialogue_lines.append(
                f"Dialogue: 0,{format_ass_time(t_start)},{format_ass_time(t_end)},"
                f"Default,,0,0,0,,{safe_text}"
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + "\n".join(dialogue_lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate ASS subtitle file from Groq word timestamps")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory")
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    timestamps_path = project_dir / "audio" / "timestamps.json"
    scenes_path = project_dir / "scenes.json"
    session_path = project_dir / "session.json"
    out_path = project_dir / "subtitles" / "story.ass"

    for p in [timestamps_path, scenes_path, session_path]:
        if not p.exists():
            print(f"ERROR: Required file not found: {p}", file=sys.stderr)
            sys.exit(1)

    ts_data = json.loads(timestamps_path.read_text(encoding="utf-8"))
    scenes_data = json.loads(scenes_path.read_text(encoding="utf-8"))
    session = json.loads(session_path.read_text(encoding="utf-8"))
    aspect_ratio = session.get("visual", {}).get("aspect_ratio", "16:9")
    if aspect_ratio == "9:16":
        width, height = 1080, 1920
    else:
        width, height = RENDER_WIDTH, RENDER_HEIGHT

    words = ts_data.get("words", [])
    scenes = scenes_data.get("scenes", [])

    font_name, font_dir = detect_devanagari_font(project_dir)
    print(f"→ Using font: {font_name}" + (f" (from {font_dir})" if font_dir else ""))
    print(f"→ Processing {len(words)} words across {len(scenes)} scenes")

    write_ass_file(words, scenes, out_path, width, height, font_name)

    subtitle_count = out_path.read_text(encoding="utf-8").count("Dialogue:")
    print(f"✓ ASS subtitle file written: {out_path}")
    print(f"  {subtitle_count} subtitle entries generated")


if __name__ == "__main__":
    main()
