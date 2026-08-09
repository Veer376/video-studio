"""
Batch generate scene images using Cloudflare Workers AI flux-2-dev model.

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

IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080


def load_env():
    env_path = Path.home() / ".config/projects/.env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_cloudflare_credentials() -> list[tuple[str, str]]:
    """
    Collect all Cloudflare (account_id, api_token) pairs from environment variables.
    Supports: CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN,
    CLOUDFLARE_ACCOUNT_ID_1 + CLOUDFLARE_API_TOKEN_1, ..., _N
    (also tolerates common typos like CLOURFLARE_ACCOUNT_ID_2).
    """
    pairs = []
    seen = set()

    def _get(key_names: list[str]) -> str:
        for k in key_names:
            v = os.environ.get(k, "").strip().strip('"').strip("'")
            if v:
                return v
        return ""

    def _add(acc: str, tok: str) -> None:
        if acc and tok and (acc, tok) not in seen:
            pairs.append((acc, tok))
            seen.add((acc, tok))

    # Base pair
    acc_base = _get(["CLOUDFLARE_ACCOUNT_ID", "CLOURFLARE_ACCOUNT_ID"])
    tok_base = _get(["CLOUDFLARE_API_TOKEN", "CLOURFLARE_API_TOKEN"])
    _add(acc_base, tok_base)

    # Numbered variants: 1...N
    idx = 1
    while True:
        acc = _get([f"CLOUDFLARE_ACCOUNT_ID_{idx}", f"CLOURFLARE_ACCOUNT_ID_{idx}"])
        tok = _get([f"CLOUDFLARE_API_TOKEN_{idx}", f"CLOURFLARE_API_TOKEN_{idx}"])
        if not acc and not tok:
            if idx > 10:
                break
            idx += 1
            continue
        _add(acc, tok)
        idx += 1

    return pairs


def generate_single_image(
    credentials: list[tuple[str, str]],
    model: str,
    prompt: str,
    width: int,
    height: int,
    out_path: Path,
    ref_image_path: Path | None = None,
    ref_weight: float | None = None,
) -> None:
    if not credentials:
        raise RuntimeError("No Cloudflare credentials provided")

    # Determine if the model requires multipart/form-data or has reference image
    has_ref = ref_image_path is not None and ref_image_path.exists()
    is_multipart = ("klein" in model or "flux-2-dev" in model or has_ref) and "schnell" not in model

    if is_multipart:
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = []
        
        fields = {
            "prompt": prompt,
            "width": str(width),
            "height": str(height),
        }
        if has_ref and ref_weight is not None:
            fields["strength"] = str(ref_weight)

        for key, value in fields.items():
            body.append(f"--{boundary}".encode("utf-8"))
            body.append(f'Content-Disposition: form-data; name="{key}"'.encode("utf-8"))
            body.append(b"")
            body.append(str(value).encode("utf-8"))

        if has_ref and ref_image_path:
            img_bytes = ref_image_path.read_bytes()
            body.append(f"--{boundary}".encode("utf-8"))
            body.append(f'Content-Disposition: form-data; name="image"; filename="{ref_image_path.name}"'.encode("utf-8"))
            body.append(b"Content-Type: image/png")
            body.append(b"")
            body.append(img_bytes)

        body.append(f"--{boundary}--".encode("utf-8"))
        body.append(b"")
        data_bytes = b"\r\n".join(body)
        content_type = f"multipart/form-data; boundary={boundary}"
    else:
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        content_type = "application/json"

    try:
        ctx = ssl._create_unverified_context()
    except Exception:
        ctx = ssl.create_default_context()

    n_creds = len(credentials)
    max_attempts = n_creds * 3

    for attempt in range(1, max_attempts + 1):
        cred_idx = (attempt - 1) % n_creds
        account_id, api_token = credentials[cred_idx]
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"

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
            with urllib.request.urlopen(req, timeout=120, context=ctx) as response:
                resp_content_type = response.headers.get("Content-Type", "")
                response_data = response.read()

                out_path.parent.mkdir(parents=True, exist_ok=True)

                if "application/json" in resp_content_type:
                    data = json.loads(response_data.decode("utf-8"))
                    if "result" in data and "image" in data["result"]:
                        img_b64 = data["result"]["image"]
                        img_bytes = base64.b64decode(img_b64)
                        out_path.write_bytes(img_bytes)
                    else:
                        raise RuntimeError(f"Unexpected Cloudflare JSON response structure: {data}")
                else:
                    out_path.write_bytes(response_data)
                
                print(f"✓ Image saved: {out_path.name}")
                return

        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            is_quota_error = exc.code == 429 or "4006" in detail or "daily free allocation" in detail or "used up your daily free allocation" in detail
            if is_quota_error and n_creds > 1:
                next_cred_idx = (cred_idx + 1) % n_creds
                print(
                    f"  Warning: Cloudflare HTTP {exc.code} quota limit on account key[{cred_idx + 1}/{n_creds}] ({account_id[:8]}...). "
                    f"Rotating to key[{next_cred_idx + 1}]...",
                    file=sys.stderr
                )
                time.sleep(1.0)
                continue
            elif exc.code in (429, 500, 503, 504) and attempt < max_attempts:
                wait = 3.0 * attempt
                print(f"  Cloudflare HTTP {exc.code} (attempt {attempt}/{max_attempts}). Retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise RuntimeError(f"Cloudflare HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < max_attempts:
                print(f"  Cloudflare network error (attempt {attempt}/{max_attempts}). Retrying...", file=sys.stderr)
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
    credentials = load_cloudflare_credentials()

    if not credentials:
        print("ERROR: No Cloudflare ACCOUNT_ID / API_TOKEN credentials found in ~/.config/projects/.env", file=sys.stderr)
        sys.exit(1)

    print(f"  Loaded {len(credentials)} Cloudflare account credential pair(s).")

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

    aspect_ratio = session.get("visual", {}).get("aspect_ratio", "16:9")
    if aspect_ratio == "9:16":
        width, height = 1080, 1920
    else:
        width, height = IMAGE_WIDTH, IMAGE_HEIGHT

    visual_style = scenes_data.get("visual_style", "premium cinematic digital painting, vivid colors")
    if isinstance(visual_style, dict):
        visual_style = visual_style.get("style", "premium cinematic digital painting, vivid colors")

    print(f"→ Generating scene images (Resolution: {width}x{height})")
    print(f"  Global Style: {visual_style}")

    # Build tasks for scene images
    scenes = scenes_data.get("scenes", [])
    characters = scenes_data.get("characters", {})
    tasks = []
    for scene in scenes:
        scene_id = scene["id"]
        out_path = project_dir / "images" / f"{scene_id}.png"
        
        if out_path.exists() and not args.force:
            scene["image_path"] = f"images/{scene_id}.png"
            continue

        full_prompt = f"{visual_style} — {scene['image_prompt']}"

        # Append referenced character visual descriptions to the prompt
        ref_chars = scene.get("referenced_characters") or scene.get("characters") or []
        for char_key in ref_chars:
            char_info = characters.get(char_key, {})
            char_desc = char_info.get("prompt", "").strip()
            canonical = char_info.get("canonical_name", char_key)
            if char_desc:
                full_prompt += f" — {canonical}: {char_desc}"

        # Resolve reference image (prior scene continuation only)
        ref_image_path = None
        ref_weight = scene.get("reference_weight", 0.65)
        ref_scene_id = scene.get("reference_scene_id") or scene.get("reference_scene_ids", [None])[0]

        if ref_scene_id and str(ref_scene_id).startswith("scene-"):
            ref_p = project_dir / "images" / f"{ref_scene_id}.png"
            if ref_p.exists():
                ref_image_path = ref_p

        tasks.append((scene, full_prompt, out_path, ref_image_path, ref_weight))

    if not tasks:
        print("✓ All images already exist. Nothing to generate.")
    else:
        print(f"→ Queueing {len(tasks)} images for generation (Concurrency: {args.concurrency})")
        
        def worker(task):
            scene, prompt, out_path, ref_path, ref_w = task
            try:
                generate_single_image(
                    credentials=credentials,
                    model=args.model,
                    prompt=prompt,
                    width=width,
                    height=height,
                    out_path=out_path,
                    ref_image_path=ref_path,
                    ref_weight=ref_w,
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



"""
MODELS:

Complete Official Catalog: Cloudflare Image Models (Grounded Real-World Neuron Pricing)

1 👑	FLUX.2 [dev]	         @cf/black-forest-labs/flux-2-dev	multipart/form-data	~2,500 – 3,500 neurons	           3 to 4 Images / Day
2 🎨	FLUX.1 [schnell] 12B	 @cf/black-forest-labs/flux-1-schnell	application/json	~1,000 – 1,200 neurons	       8 to 10 Images / Day
3 ⚡	FLUX.2 [klein] 4B	         @cf/black-forest-labs/flux-2-klein-4b	multipart/form-data	~500 – 800 neurons	           12 to 20 Images / Day
4 ✨	Leonardo Phoenix 1.0	    @cf/leonardo/phoenix-1.0	application/json	~800 – 1,500 neurons	                 6 to 12 Images / Day
5 🖌️	Leonardo Lucid Origin	  @cf/leonardo/lucid-origin	application/json	~800 – 1,500 neurons	                   6 to 12 Images / Day
6 ⚡	SDXL-Lightning	             @cf/bytedance/stable-diffusion-xl-lightning	application/json	~150 – 250 neurons	  40 to 65 Images / Day
7 🎭	DreamShaper 8 LCM	     @cf/lykon/dreamshaper-8-lcm	application/json	~100 – 200 neurons	                  50 to 100 Images / Day
8 🖼️	SDXL Base 1.0	          @cf/stabilityai/stable-diffusion-xl-base-1.0	application/json	~300 – 600 neurons	   15 to 30 Images / Day
9 🛠️	DreamShaper 8 Inpainting  @cf/lykon/dreamshaper-8-inpainting	application/json	~200 – 400 neurons	           25 to 50 Images / Day
10 🛠️	SD 1.5 Inpainting	      @cf/runwayml/stable-diffusion-v1-5-inpainting	application/json	~150 – 300 neurons	   30 to 60 Images / Day
11 🔄	SD 1.5 Img2Img	         @cf/stabilityai/stable-diffusion-v1-5-img2img	application/json	~100 – 200 neurons	  50 to 100 Images / Day
"""
