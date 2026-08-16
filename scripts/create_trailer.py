#!/usr/bin/env python3
"""
create_trailer.py - Premium YouTube Cinematic Trailer / Intro Hook Generator
for 'Chhotu Motu Ka Rocket Tractor — Chand Ka Amrit'.
Matches YouTube 3D animation channel aesthetic: ultra-bold rounded cream typography,
thick dark outline, zero obstructive boxes, minimal text, non-stop fast-paced flow.
"""

import os
import sys
import subprocess
from PIL import Image, ImageDraw, ImageFont

VIDEO_DIR = "stories/chhotu-motu-rocket-tractor/videos"
OUTPUT_DIR = "stories/chhotu-motu-rocket-tractor/output"
TEMP_DIR = "stories/chhotu-motu-rocket-tractor/temp/trailer_build"
TRAILER_MP4 = os.path.join(OUTPUT_DIR, "trailer.mp4")
FULL_MOVIE_WITH_HOOK = os.path.join(OUTPUT_DIR, "full_movie_with_trailer_hook.mp4")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"

def render_cartoon_text_overlay(lines, font_size=72, y_pos=580, stroke_w=10, out_path="/tmp/ov.png"):
    """
    Renders ultra-clean, minimal cartoon-style text overlay with thick dark outline
    and subtle 3D shadow, exactly matching YouTube animation channel standards.
    No obstructive boxes or dark pill rectangles.
    """
    img = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, font_size)
    
    line_h = font_size + 14
    total_h = len(lines) * line_h
    start_y = y_pos - (total_h // 2)
    
    fill_col = (255, 253, 240, 255)    # Warm creamy white / ivory
    stroke_col = (18, 18, 18, 255)     # Dark charcoal / black outline
    shadow_col = (0, 0, 0, 220)        # Soft clean drop shadow
    
    for i, line in enumerate(lines):
        y = start_y + i * line_h
        # 3D Drop shadow (+7px y-offset)
        draw.text((640, y + 7), line, font=font, fill=shadow_col, stroke_width=stroke_w, stroke_fill=shadow_col, anchor="mm")
        # Main text with thick rounded stroke
        draw.text((640, y), line, font=font, fill=fill_col, stroke_width=stroke_w, stroke_fill=stroke_col, anchor="mm")
        
    img.save(out_path)
    return out_path

def cut_clip(scene_id, start_s, dur_s, speed, overlay_png, out_file):
    """Extract, speed-ramp, optionally apply transparent overlay, and normalize video/audio."""
    src = os.path.join(VIDEO_DIR, f"{scene_id}.mp4")
    if not os.path.exists(src):
        raise FileNotFoundError(f"Source video {src} not found!")
        
    vf_parts = []
    if abs(speed - 1.0) > 0.01:
        vf_parts.append(f"setpts={1.0/speed:.4f}*PTS")
    vf_parts.append("scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24")
    
    af_parts = []
    if abs(speed - 1.0) > 0.01:
        af_parts.append(f"atempo={speed:.4f}")
    af_parts.append("aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo")
    
    cmd = ["ffmpeg", "-y", "-ss", str(start_s), "-t", str(dur_s), "-i", src]
    if overlay_png and os.path.exists(overlay_png):
        cmd.extend(["-loop", "1", "-i", overlay_png])
        vf_str = ",".join(vf_parts)
        complex_filter = f"[0:v]{vf_str}[v0];[v0][1:v]overlay=0:0:shortest=1[vout]"
        cmd.extend([
            "-filter_complex", complex_filter,
            "-map", "[vout]",
            "-map", "0:a"
        ])
    else:
        cmd.extend([
            "-vf", ",".join(vf_parts),
            "-map", "0:v",
            "-map", "0:a"
        ])
        
    cmd.extend([
        "-af", ",".join(af_parts),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        out_file
    ])
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error processing {scene_id}: {res.stderr}")
        raise RuntimeError(f"FFmpeg failed on {scene_id}")

def main():
    print("=== STEP 1: Generating Minimal Cartoon-Style Typography Overlays ===")
    # 4 ultra-punchy, minimal titles matching the YouTube cartoon aesthetic
    ov_crisis = render_cartoon_text_overlay(["ONLY 24 HOURS!"], font_size=82, y_pos=590, stroke_w=11, out_path=os.path.join(TEMP_DIR, "ov_crisis.png"))
    ov_jugaad = render_cartoon_text_overlay(["DESI JUGAAD!"], font_size=82, y_pos=590, stroke_w=11, out_path=os.path.join(TEMP_DIR, "ov_jugaad.png"))
    ov_space  = render_cartoon_text_overlay(["MISSION MOON!"], font_size=82, y_pos=590, stroke_w=11, out_path=os.path.join(TEMP_DIR, "ov_space.png"))
    ov_save   = render_cartoon_text_overlay(["CAN THEY SAVE", "THE VILLAGE?"], font_size=74, y_pos=580, stroke_w=11, out_path=os.path.join(TEMP_DIR, "ov_save.png"))
    
    # Final Stinger Call to Action on s060 (centered stacked text, exactly like user reference)
    ov_stinger = render_cartoon_text_overlay(["SUBSCRIBE", "TO WATCH", "COMPLETE VIDEO"], font_size=74, y_pos=340, stroke_w=12, out_path=os.path.join(TEMP_DIR, "ov_stinger.png"))
    
    print("=== STEP 2: Precision Sub-Clip Cutting & Speed-Ramping (Seamless Flow) ===")
    clips_manifest = [
        # (scene_id, start_s, dur_s, speed, overlay, out_name)
        ("s002", 0.0, 2.5, 1.25, None, "part_01.mp4"),        # Drought / well establishing shot
        ("s003", 0.5, 2.5, 1.25, ov_crisis, "part_02.mp4"),   # Sahukar hammer: "ONLY 24 HOURS!"
        ("s008", 2.2, 2.6, 1.25, ov_jugaad, "part_03.mp4"),   # Tarp reveal: "DESI JUGAAD!"
        ("s012", 7.5, 2.0, 1.25, None, "part_04.mp4"),        # Anvil hammer sparks explosion
        ("s021", 6.8, 3.2, 1.00, None, "part_05.mp4"),        # Chhotu: "जय जवान, जय किसान! रॉकेट चालू!"
        ("s022", 6.5, 3.0, 1.25, None, "part_06.mp4"),        # Tractor liftoff into twilight sky
        ("s024", 3.8, 3.0, 1.25, ov_space, "part_07.mp4"),    # Cloud burst into space: "MISSION MOON!"
        ("s029", 4.2, 3.0, 1.25, None, "part_08.mp4"),        # Motu zero-g wrench repair
        ("s036", 0.0, 3.0, 1.00, None, "part_09.mp4"),        # Moon landing touchdown
        ("s038", 3.8, 2.8, 1.00, None, "part_10.mp4"),        # Crystal cavern floating Amrit
        ("s039", 0.0, 3.2, 1.00, None, "part_11.mp4"),        # Pouring golden Amrit into Kalash
        ("s047", 0.0, 2.5, 1.25, ov_save, "part_12.mp4"),     # Re-entry plasma: "CAN THEY SAVE THE VILLAGE?"
        ("s049", 2.8, 3.0, 1.25, None, "part_13.mp4"),        # Banarasi saree parachutes
        ("s054", 0.0, 3.5, 1.25, None, "part_14.mp4"),        # 120-ft water geyser & double rainbow
        ("s056", 6.8, 3.0, 1.25, None, "part_15.mp4"),        # Sahukar mud splash
        ("s059", 6.5, 3.0, 1.25, None, "part_16.mp4"),        # Grand Bhangra celebration
        ("s060", 6.5, 3.5, 1.00, ov_stinger, "part_17.mp4"),   # Chhotu Mars blueprint wink: "SUBSCRIBE TO WATCH COMPLETE VIDEO"
    ]
    
    rendered_clips = []
    for sc_id, st, dur, spd, ov, out_name in clips_manifest:
        out_p = os.path.join(TEMP_DIR, out_name)
        print(f"Cutting {sc_id} (start={st}s, dur={dur}s, spd={spd}x) -> {out_name}")
        cut_clip(sc_id, st, dur, spd, ov, out_p)
        rendered_clips.append(out_p)
        
    print("=== STEP 3: Concatenating Trailer Clips with Synchronized Audio ===")
    concat_list_p = os.path.join(TEMP_DIR, "concat_trailer.txt")
    with open(concat_list_p, "w") as f:
        for c in rendered_clips:
            f.write(f"file '{os.path.abspath(c)}'\n")
            
    concat_cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_p,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        TRAILER_MP4
    ]
    subprocess.run(concat_cmd, check=True)
    print(f"SUCCESS: Standalone Trailer rendered to {TRAILER_MP4}")
    
    print("=== STEP 4: Creating Full Movie Master with Trailer Hook ===")
    full_concat_list_p = os.path.join(TEMP_DIR, "concat_full_movie.txt")
    with open(full_concat_list_p, "w") as f:
        f.write(f"file '{os.path.abspath(TRAILER_MP4)}'\n")
        # Add all 60 canonical scene files
        for i in range(1, 61):
            sc_path = os.path.abspath(os.path.join(VIDEO_DIR, f"s{i:03d}.mp4"))
            if os.path.exists(sc_path):
                f.write(f"file '{sc_path}'\n")
                
    full_cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", full_concat_list_p,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        FULL_MOVIE_WITH_HOOK
    ]
    subprocess.run(full_cmd, check=True)
    print(f"SUCCESS: Full Movie with Trailer Hook rendered to {FULL_MOVIE_WITH_HOOK}")

if __name__ == "__main__":
    main()
