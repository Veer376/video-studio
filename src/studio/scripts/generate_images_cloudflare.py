"""
Batch generate scene images using Cloudflare Workers AI flux-1-schnell model.

Usage:
    python3 generate_images.py --project-dir library/2026-08-01_krishna-motivation
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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def load_env():
    env_path = Path.home() / ".config/projects/.env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def generate_single_image(account_id: str, api_token: str, model: str, prompt: str, width: int, height: int, out_path: Path) -> None:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"

    # Determine if the model requires multipart/form-data (like flux-2-klein-4b)
    is_multipart = "klein" in model

    if is_multipart:
        fields = {
            "prompt": prompt,
            "width": width,
            "height": height
        }
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = []
        for key, value in fields.items():
            body.append(f"--{boundary}".encode("utf-8"))
            body.append(f'Content-Disposition: form-data; name="{key}"'.encode("utf-8"))
            body.append(b"")
            body.append(str(value).encode("utf-8"))
        body.append(f"--{boundary}--".encode("utf-8"))
        body.append(b"")
        data_bytes = b"\r\n".join(body)
        content_type = f"multipart/form-data; boundary={boundary}"
    else:
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        content_type = "application/json"

    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": content_type,
            "User-Agent": "story-video-maker/0.1"
        },
        method="POST"
    )

    try:
        ctx = ssl._create_unverified_context()
    except Exception:
        ctx = ssl.create_default_context()

    # Retry loop for rate limits or transient errors
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=120, context=ctx) as response:
                content_type = response.headers.get("Content-Type", "")
                response_data = response.read()

                out_path.parent.mkdir(parents=True, exist_ok=True)

                if "application/json" in content_type:
                    data = json.loads(response_data.decode("utf-8"))
                    if "result" in data and "image" in data["result"]:
                        img_b64 = data["result"]["image"]
                        img_bytes = base64.b64decode(img_b64)
                        out_path.write_bytes(img_bytes)
                    else:
                        raise RuntimeError(f"Unexpected Cloudflare JSON response structure: {data}")
                else:
                    # Raw binary image bytes
                    out_path.write_bytes(response_data)
                
                print(f"✓ Image saved: {out_path.name}")
                return

        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code in (429, 500, 503, 504) and attempt < 3:
                wait = 3.0 * attempt
                print(f"  Cloudflare HTTP {exc.code} (attempt {attempt}/3). Retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise RuntimeError(f"Cloudflare HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < 3:
                print(f"  Cloudflare network error (attempt {attempt}/3). Retrying...", file=sys.stderr)
                time.sleep(3.0)
            else:
                raise RuntimeError(f"Cloudflare network error: {exc.reason}") from exc


def main():
    parser = argparse.ArgumentParser(description="Batch generate scene images using Cloudflare Workers AI")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory")
    parser.add_argument("--force", action="store_true", help="Re-generate even if image already exists")
    parser.add_argument("--model", default="@cf/black-forest-labs/flux-2-klein-4b", help="Cloudflare AI model to use")
    parser.add_argument("--concurrency", type=int, default=2, help="Number of parallel generation threads")
    args = parser.parse_args()

    load_env()
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()

    if not account_id or not api_token:
        print("ERROR: CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN not found in ~/.config/projects/.env", file=sys.stderr)
        sys.exit(1)

    project_dir = Path(args.project_dir)
    session_path = project_dir / "session.json"
    scenes_path = project_dir / "scenes.json"

    if not session_path.exists():
        print(f"ERROR: session.json not found at {session_path}", file=sys.stderr)
        sys.exit(1)
    if not scenes_path.exists():
        print(f"ERROR: scenes.json not found at {scenes_path}", file=sys.stderr)
        sys.exit(1)

    session = json.loads(session_path.read_text(encoding="utf-8"))
    scenes_data = json.loads(scenes_path.read_text(encoding="utf-8"))

    # Map aspect ratio to width/height
    aspect_ratio = session.get("video", {}).get("aspect_ratio", "16:9")
    if aspect_ratio == "16:9":
        width, height = 1024, 576
    elif aspect_ratio == "9:16":
        width, height = 576, 1024
    else:
        width, height = 768, 768

    visual_style = scenes_data.get("visual_style", "premium cinematic digital painting, vivid colors")
    if isinstance(visual_style, dict):
        visual_style = visual_style.get("style", "premium cinematic digital painting, vivid colors")

    print(f"→ Generating scene images (Resolution: {width}x{height})")
    print(f"  Global Style: {visual_style}")

    scenes = scenes_data.get("scenes", [])
    
    # We will build a list of tasks to execute
    tasks = []
    for scene in scenes:
        scene_id = scene["id"]
        out_path = project_dir / "images" / f"{scene_id}.png"
        
        if out_path.exists() and not args.force:
            # Already exists, just make sure path is written in scenes.json
            scene["image_path"] = f"images/{scene_id}.png"
            continue

        full_prompt = f"{visual_style} — {scene['image_prompt']}"
        tasks.append((scene, full_prompt, out_path))

    if not tasks:
        print("✓ All images already exist. Nothing to generate.")
    else:
        print(f"→ Queueing {len(tasks)} images for generation (Concurrency: {args.concurrency})")
        
        def worker(task):
            scene, prompt, out_path = task
            try:
                generate_single_image(
                    account_id=account_id,
                    api_token=api_token,
                    model=args.model,
                    prompt=prompt,
                    width=width,
                    height=height,
                    out_path=out_path
                )
                scene["image_path"] = f"images/{scene['id']}.png"
                return True
            except Exception as e:
                print(f"✗ Failed to generate image for {scene['id']}: {e}", file=sys.stderr)
                return False

        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            results = list(executor.map(worker, tasks))

        success_count = sum(1 for r in results if r)
        print(f"→ Batch generation complete: {success_count}/{len(tasks)} succeeded.")

    # Write updated scenes.json manifest
    scenes_path.write_text(json.dumps(scenes_data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Update session status only when every scene has a concrete image on disk.
    if scenes and all((project_dir / "images" / f"{s['id']}.png").exists() for s in scenes):
        session["session"]["status"] = "illustrate_complete"
        session_path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
        print("✓ session.json status updated to: illustrate_complete")
    else:
        missing = [
            s["id"]
            for s in scenes
            if not (project_dir / "images" / f"{s['id']}.png").exists()
        ]
        print(f"ERROR: Missing images after generation: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
