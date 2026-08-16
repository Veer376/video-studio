#!/usr/bin/env python3
"""
Assemble the 5 vertical beats into the official YouTube Short (9:16 portrait format).
Includes ultra-bold cartoon typography overlays with thick outlines and drop shadow.
"""
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SHORTS_DIR = Path("/Users/aryaveer/Projects/video-project/stories/chhotu-motu-rocket-tractor/shorts")
OUTPUT_DIR = Path("/Users/aryaveer/Projects/video-project/stories/chhotu-motu-rocket-tractor/output")
TEMP_DIR = SHORTS_DIR / "temp_render"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BEATS = [
    {
        "file": SHORTS_DIR / "short_01_launch.mp4",
        "text_cues": [
            {"text": "108 ROCKETS JUGAAD!", "start": 0.5, "end": 4.0, "y_pos": 0.12, "color": "#FFFDF0"}
        ]
    },
    {
        "file": SHORTS_DIR / "short_02_orbit.mp4",
        "text_cues": [
            {"text": "DESTINATION MOON!", "start": 0.5, "end": 4.0, "y_pos": 0.12, "color": "#FFFDF0"}
        ]
    },
    {
        "file": SHORTS_DIR / "short_03_lunar_cavern.mp4",
        "text_cues": [
            {"text": "JADUI AMRIT FOUND!", "start": 0.5, "end": 4.0, "y_pos": 0.12, "color": "#FFFDF0"}
        ]
    },
    {
        "file": SHORTS_DIR / "short_04_reentry.mp4",
        "text_cues": [
            {"text": "BANARASI SAREE PARACHUTE!", "start": 6.5, "end": 9.8, "y_pos": 0.12, "color": "#FFFDF0"}
        ]
    },
    {
        "file": SHORTS_DIR / "short_05_geyser_cta.mp4",
        "text_cues": [
            {"text": "RAMPUR IS SAVED!", "start": 3.5, "end": 6.5, "y_pos": 0.12, "color": "#FFFDF0"},
            {"text": "WATCH FULL MOVIE NOW!", "start": 6.8, "end": 10.0, "y_pos": 0.82, "color": "#FFE600"}
        ]
    }
]

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"

def make_text_overlay(text, color="#FFFDF0", width=720, height=1280, font_size=46):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    x = (width - text_w) // 2
    return img, font, (text_w, text_h)

def render_segment_with_text(beat_idx, beat_info):
    src_file = beat_info["file"]
    out_file = TEMP_DIR / f"seg_{beat_idx:02d}.mp4"
    
    cues = beat_info.get("text_cues", [])
    if not cues:
        # Just copy/standardize
        cmd = [
            "ffmpeg", "-y", "-i", str(src_file),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
            "-c:a", "aac", "-ar", "48000", "-ac", "2",
            str(out_file)
        ]
        subprocess.run(cmd, check=True)
        return out_file

    # Build complex filter for text overlays
    filter_complex = []
    input_args = ["-i", str(src_file)]
    
    overlay_idx = 1
    last_v = "0:v"
    
    for c_idx, cue in enumerate(cues):
        overlay_img_path = TEMP_DIR / f"overlay_{beat_idx:02d}_{c_idx}.png"
        img = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype(FONT_PATH, 44)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), cue["text"], font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (720 - text_w) // 2
        y = int(1280 * cue["y_pos"])

        # Draw 3D shadow + thick outline + fill
        shadow_color = (0, 0, 0, 230)
        outline_color = (18, 18, 18, 255)
        
        # Shadow offset
        draw.text((x + 4, y + 6), cue["text"], font=font, fill=shadow_color, stroke_width=12, stroke_fill=shadow_color)
        # Main thick outline
        draw.text((x, y), cue["text"], font=font, fill=cue["color"], stroke_width=10, stroke_fill=outline_color)
        
        img.save(overlay_img_path)
        input_args.extend(["-i", str(overlay_img_path)])
        
        next_v = f"v{c_idx+1}"
        enable_expr = f"between(t,{cue['start']},{cue['end']})"
        filter_complex.append(f"[{last_v}][{overlay_idx}:v]overlay=0:0:enable='{enable_expr}'[{next_v}]")
        last_v = next_v
        overlay_idx += 1

    cmd = ["ffmpeg", "-y"] + input_args + [
        "-filter_complex", ";".join(filter_complex),
        "-map", f"[{last_v}]",
        "-map", "0:a?",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
        "-c:a", "aac", "-ar", "48000", "-ac", "2",
        str(out_file)
    ]
    subprocess.run(cmd, check=True)
    return out_file

def main():
    print("Rendering vertical Short segments with clean typography...")
    rendered_segs = []
    for idx, beat in enumerate(BEATS):
        seg_path = render_segment_with_text(idx, beat)
        rendered_segs.append(seg_path)
        print(f"✓ Rendered segment {idx+1}: {seg_path}")

    # Concat list
    concat_txt = TEMP_DIR / "concat_list.txt"
    with open(concat_txt, "w") as f:
        for seg in rendered_segs:
            f.write(f"file '{seg.resolve()}'\n")

    final_output = OUTPUT_DIR / "chhotu_motu_short_vertical.mp4"
    concat_cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_txt),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        str(final_output)
    ]
    subprocess.run(concat_cmd, check=True)
    print(f"\n🎉 Successfully rendered YouTube Short: {final_output}")

if __name__ == "__main__":
    main()
