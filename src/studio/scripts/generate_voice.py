"""
Generate full narration audio from script.md using Gemini TTS.

Usage:
    python3 generate_audio.py --project-dir library/2026-08-01_krishna-motivation
"""
import argparse
import base64
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path


def load_env():
    env_path = Path.home() / ".config/projects/.env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_api_keys() -> list[str]:
    keys = []
    # Collect all GEMINI_API_KEY variants
    for k, v in os.environ.items():
        if k == "GEMINI_API_KEY" or k.startswith("GEMINI_API_KEY_"):
            val = v.strip().strip('"').strip("'")
            if val and val not in keys:
                keys.append(val)
    return keys


def extract_narration(script_path: Path) -> str:
    """
    Strip script.md metadata header and return only the narration body.
    Everything after the first '---' separator is the story prose.
    """
    content = script_path.read_text(encoding="utf-8")
    # Split on the first '---' separator
    parts = content.split("---", 1)
    if len(parts) == 2:
        narration = parts[1].strip()
    else:
        # No separator found — use full content minus the first title line
        lines = content.splitlines()
        narration = "\n".join(lines[1:]).strip()
    return narration


def call_gemini_tts(api_key: str, model: str, voice: str, text: str, out_path: Path) -> None:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice}
                }
            }
        }
    }

    ctx = ssl._create_unverified_context()

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "story-video-maker/0.1"},
        method="POST",
    )

    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))

            parts = res_data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            if not parts:
                raise RuntimeError(f"No parts in Gemini TTS response: {res_data}")

            audio_b64 = parts[0].get("inlineData", {}).get("data")
            if not audio_b64:
                raise RuntimeError(f"No audio data in Gemini TTS response: {res_data}")

            raw_pcm = base64.b64decode(audio_b64)

            # Gemini returns little-endian 16-bit PCM at 24000 Hz
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(out_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(raw_pcm)

            print(f"✓ Audio written to: {out_path}")
            return

        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code in (429, 500, 503, 504) and attempt < 5:
                wait = 2.0 * (2 ** (attempt - 1))
                print(f"  HTTP {exc.code} — retrying in {wait:.1f}s... (attempt {attempt}/5)", file=sys.stderr)
                time.sleep(wait)
            else:
                raise RuntimeError(f"Gemini TTS HTTP {exc.code}: {detail}") from exc

        except urllib.error.URLError as exc:
            if attempt < 5:
                wait = 2.0 * (2 ** (attempt - 1))
                print(f"  Network error ({exc.reason}) — retrying in {wait:.1f}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise RuntimeError(f"Gemini TTS network error: {exc.reason}") from exc


def concatenate_wav_files(input_paths: list[Path], output_path: Path) -> None:
    if not input_paths:
        return
    with wave.open(str(input_paths[0]), "rb") as wav_in:
        params = wav_in.getparams()
    with wave.open(str(output_path), "wb") as wav_out:
        wav_out.setparams(params)
        for path in input_paths:
            with wave.open(str(path), "rb") as wav_in:
                wav_out.writeframes(wav_in.readframes(wav_in.getnframes()))


def main():
    parser = argparse.ArgumentParser(description="Generate full narration audio using Gemini TTS")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory (e.g. library/2026-08-01_krishna-motivation)")
    parser.add_argument("--force", action="store_true", help="Re-generate even if narration.wav already exists")
    parser.add_argument("--voice", help="Override the voice configuration (e.g. Puck, Aoede, Schedar, Charon, Kore, Fenrir)")
    parser.add_argument("--no-split", action="store_true", help="Do not split by paragraphs, generate full text at once in one request")
    args = parser.parse_args()

    load_env()
    api_keys = load_api_keys()
    if not api_keys:
        print("ERROR: No Gemini API keys found. Set GEMINI_API_KEY in ~/.config/projects/.env", file=sys.stderr)
        sys.exit(1)

    project_dir = Path(args.project_dir)
    session_path = project_dir / "session.json"
    script_path = project_dir / "script.md"
    out_path = project_dir / "audio" / "narration.wav"

    if not session_path.exists():
        print(f"ERROR: session.json not found at {session_path}", file=sys.stderr)
        sys.exit(1)
    if not script_path.exists():
        print(f"ERROR: script.md not found at {script_path}", file=sys.stderr)
        sys.exit(1)
    if out_path.exists() and not args.force:
        print(f"✓ narration.wav already exists. Use --force to regenerate.")
        sys.exit(0)

    session = json.loads(session_path.read_text(encoding="utf-8"))
    model = session.get("voice", {}).get("model", "gemini-3.1-flash-tts-preview")
    voice = args.voice or session.get("voice", {}).get("voice", "Puck")

    narration = extract_narration(script_path)
    
    # Split by paragraph
    paragraphs = [p.strip() for p in narration.split("\n\n") if p.strip()]

    # If --no-split is specified, or only 1 paragraph, generate all at once (fallback)
    if args.no_split or len(paragraphs) <= 1:
        word_count = len(narration.split())
        print(f"→ Generating full audio in a single request for {word_count} words")
        print(f"  Model: {model} | Voice: {voice}")
        for key in api_keys:
            try:
                call_gemini_tts(api_key=key, model=model, voice=voice, text=narration, out_path=out_path)
                return
            except RuntimeError as e:
                if "400" in str(e) or "403" in str(e):
                    print(f"  Key failed ({str(e)[:60]}...) — trying next key", file=sys.stderr)
                    continue
                raise
        print("ERROR: All Gemini API keys exhausted.", file=sys.stderr)
        sys.exit(1)
    else:
        # Generate paragraph-by-paragraph (default behavior now)
        print(f"→ Generating audio paragraph-by-paragraph and concatenating ({len(paragraphs)} paragraphs)")
        print(f"  Model: {model} | Voice: {voice} | Unique Keys Available: {len(api_keys)}")
        
        temp_dir = project_dir / "audio" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        temp_files = []
        for i, paragraph_text in enumerate(paragraphs):
            p_id = f"paragraph-{i+1:03d}"
            p_wav = temp_dir / f"{p_id}.wav"
            temp_files.append(p_wav)
            
            # Select key using round-robin rotation across the list of unique keys
            key_index = i % len(api_keys)
            key = api_keys[key_index]
            
            print(f"  Generating audio for {p_id} ({len(paragraph_text.split())} words) using Key {key_index + 1}/{len(api_keys)}...")
            
            success = False
            try:
                call_gemini_tts(api_key=key, model=model, voice=voice, text=paragraph_text, out_path=p_wav)
                success = True
            except RuntimeError as e:
                print(f"    Warning: Key {key_index + 1} failed: {e}. Trying fallback keys...")
                # Fallback to other keys if the primary key fails
                for alt_key in api_keys:
                    if alt_key == key:
                        continue
                    try:
                        call_gemini_tts(api_key=alt_key, model=model, voice=voice, text=paragraph_text, out_path=p_wav)
                        success = True
                        break
                    except Exception:
                        continue
            if not success:
                print(f"ERROR: Failed to generate audio for {p_id}", file=sys.stderr)
                sys.exit(1)
                
        # Concatenate temp files into out_path
        print(f"→ Concatenating {len(temp_files)} paragraph audio clips into {out_path}...")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        concatenate_wav_files(temp_files, out_path)
        
        # Clean up temp files
        for f in temp_files:
            try:
                f.unlink()
            except Exception:
                pass
        try:
            temp_dir.rmdir()
        except Exception:
            pass
            
        print(f"✓ Concatenated audio written to: {out_path}")


if __name__ == "__main__":
    main()
