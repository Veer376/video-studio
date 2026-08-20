"""Google Flow video generation provider connecting to the local Flow agent server."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

try:
    from .base import (
        BaseProvider,
        CompiledScene,
        CreditError,
        ProviderUnavailableError,
        VideoError,
    )
except ImportError:
    from base import (  # type: ignore
        BaseProvider,
        CompiledScene,
        CreditError,
        ProviderUnavailableError,
        VideoError,
    )


DEFAULT_HOST = "127.0.0.1:8001"
POLL_INTERVAL = 3
CREDIT_COSTS = {4: 5, 6: 10, 8: 15, 10: 20}

VIDEO_MODEL_MAP = {
    "omni_flash": None,
    "omni-flash": None,
    "gemini-omni-flash-preview": None,
    "gemini-omni-flash": None,
    "gemini_omni_flash": None,
    "omni": None,
    "flash": None,
    "default": None,
    "abra": None,
    "veo": "veo_2",
    "veo_2": "veo_2",
}


@dataclass(frozen=True)
class FlowSceneInput:
    """Provider-native inputs derived from one compiled project scene."""

    prompt: str
    images: Sequence[Path]
    start_frame: Path | None


def requires_google_fallback(
    compiled: CompiledScene,
    first_frame: Path | None,
) -> bool:
    """Return whether Flow would have to discard required references."""
    return first_frame is not None and len(compiled.images) > 1


def prepare_scene_input(
    compiled: CompiledScene,
    first_frame: Path | None,
) -> FlowSceneInput:
    """Serialize a compiled scene for the Flow endpoint without changing its source prompt."""
    prompt = compiled.annotated_prompt or compiled.raw_prompt
    if not prompt.strip():
        raise VideoError("Compiled Flow scene has no authoring prompt")

    if first_frame is not None:
        if requires_google_fallback(compiled, first_frame):
            raise VideoError(
                "Flow cannot combine the literal start frame with the scene's "
                "required references; route this scene through Google"
            )
        return FlowSceneInput(
            prompt="Use the supplied start image as the exact first frame. " + prompt,
            images=(),
            start_frame=first_frame,
        )

    if compiled.handle_order:
        bindings = "\n".join(
            f"- Reference image {index} depicts {handle}."
            for index, handle in enumerate(compiled.handle_order, 1)
        )
        prompt = f"REFERENCE IMAGE BINDINGS:\n{bindings}\n\n{prompt}"

    return FlowSceneInput(
        prompt=prompt,
        images=tuple(compiled.images),
        start_frame=None,
    )


def _base_url(host: str) -> str:
    return f"http://{host}"


def _get(url: str, timeout: int = 30) -> dict[str, Any]:
    with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
        return json.loads(r.read().decode())


def _post(url: str, body: dict[str, Any], headers: dict[str, str] | None = None, timeout: int = 240) -> dict[str, Any]:
    data = json.dumps(body).encode()
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _post_err(exc: urllib.error.HTTPError) -> str:
    try:
        return json.loads(exc.read().decode()).get("detail", str(exc))
    except Exception:
        return str(exc)


import hashlib

def _get_cache_path() -> Path:
    cache_dir = Path.home() / ".cache" / "flow_video"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "media_ids.json"


def _load_upload_cache() -> dict[str, str]:
    cache_path = _get_cache_path()
    if cache_path.is_file():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_upload_cache(cache: dict[str, str]) -> None:
    try:
        cache_path = _get_cache_path()
        cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception:
        pass


def is_media_valid(base: str, media_id: str) -> bool:
    """Verify directly with Flow Agent server that media_id has an active, signed Google CDN URL."""
    if not media_id:
        return False
    try:
        res = _get(f"{base}/v1/media/{media_id}/url", timeout=10)
        return bool(res.get("url"))
    except Exception:
        return False


def upload_media_file(base: str, path: Path, label: str = "file") -> tuple[str, bool]:
    """Upload a local image or video file to Flow server and return (media_id, is_fresh_upload).
    
    Guarantees that the returned media_id is valid, active, and verified against Flow.
    """
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")

    raw = path.read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()
    cache = _load_upload_cache()

    # 1. Check local persistent disk cache first
    if file_hash in cache:
        cached_id = cache[file_hash]
        if is_media_valid(base, cached_id):
            return cached_id, False
        # Cached ID is expired/invalid on Google Flow -> invalidate entry
        del cache[file_hash]
        _save_upload_cache(cache)

    # 2. Check active Flow server history registry for previously uploaded identical content
    try:
        h = _get(f"{base}/v1/history?limit=100")
        hist = h.get("history", [])
        for item in hist:
            if item.get("fingerprint") == file_hash and item.get("media_id"):
                candidate_id = str(item["media_id"])
                if is_media_valid(base, candidate_id):
                    cache[file_hash] = candidate_id
                    _save_upload_cache(cache)
                    return candidate_id, False
    except Exception:
        pass

    # 3. If not cached or expired, perform a fresh upload
    if raw[:4] == b"\x89PNG":
        mime = "image/png"
    elif raw[:2] == b"\xff\xd8":
        mime = "image/jpeg"
    elif raw[:4] == b"RIFF" and len(raw) > 12 and raw[8:12] == b"WEBP":
        mime = "image/webp"
    elif len(raw) > 12 and raw[4:8] == b"ftyp":
        mime = "video/mp4"
    else:
        ext = path.suffix.lower()
        mime = "video/mp4" if ext in {".mp4", ".mov", ".m4v"} else "image/jpeg"

    b64 = base64.b64encode(raw).decode("ascii")
    try:
        res = _post(f"{base}/v1/upload", {"image_base64": f"data:{mime};base64,{b64}"})
        media_id = res.get("media_id")
        if not media_id:
            raise VideoError(f"Upload succeeded but returned no media_id: {res}")
        media_id_str = str(media_id)

        # 4. Proactive Readiness check: poll up to 10s until Google Flow indexing confirms the media is ready
        for _ in range(10):
            if is_media_valid(base, media_id_str):
                break
            time.sleep(1.0)

        cache[file_hash] = media_id_str
        _save_upload_cache(cache)
        return media_id_str, True
    except urllib.error.HTTPError as exc:
        raise VideoError(f"Failed to upload {label} ({path.name}): {_post_err(exc)}") from exc
    except Exception as exc:
        raise VideoError(f"Failed to upload {label} ({path.name}): {exc}") from exc


class FlowProvider(BaseProvider):
    """Generates videos via Google Flow local agent server."""

    name = "flow"

    def __init__(self, host: str = DEFAULT_HOST) -> None:
        self.host = host
        self.base = _base_url(host)

    def preflight(self) -> bool:
        """Check backend health, Chrome extension connection, and captured Flow auth key."""
        try:
            h = _get(f"{self.base}/health", timeout=5)
        except Exception as exc:
            raise ProviderUnavailableError(
                f"Flow backend not reachable at {self.base}. "
                "Start it with: ~/.local/bin/flow"
            ) from exc

        if not h.get("extension_connected"):
            raise ProviderUnavailableError(
                "Flow Chrome extension is not connected. "
                "Open Chrome, check extension at chrome://extensions, and refresh https://labs.google/fx/tools/flow"
            )
        if not h.get("has_flow_key"):
            raise ProviderUnavailableError(
                "Flow key not captured. Open https://labs.google/fx/tools/flow and sign in."
            )
        return True

    def check_credits(self, duration: int = 10, count: int = 1) -> bool:
        cost_each = CREDIT_COSTS.get(duration, 20)
        total_cost = cost_each * count
        try:
            cdata = _get(f"{self.base}/v1/credits", timeout=10)
            total = cdata.get("total_credits", 0)
            if total < total_cost:
                raise CreditError(
                    f"Insufficient Flow credits: {total} available, {total_cost} needed ({cost_each}×{count} for {duration}s)"
                )
            return True
        except CreditError:
            raise
        except Exception as exc:
            print(f"Warning: Could not verify Flow credits: {exc}")
            return True

    def generate_video(
        self,
        *,
        prompt: str,
        output: Path,
        images: Sequence[Path] = (),
        videos: Sequence[Path] = (),
        task: str | None = None,
        aspect_ratio: str = "16:9",
        duration: int = 10,
        model: str | None = None,
        start_frame: Path | None = None,
        end_frame: Path | None = None,
        poll_timeout: int = 300,
        **kwargs: Any,
    ) -> int:
        if not isinstance(prompt, str) or not prompt.strip():
            raise VideoError("Flow requires a non-empty prompt")
        if duration not in CREDIT_COSTS:
            raise VideoError(
                f"Flow duration must be one of {sorted(CREDIT_COSTS)} seconds; received {duration}"
            )
        if len(images) > 10:
            raise VideoError("Flow accepts at most 10 reference images")
        if end_frame is not None and start_frame is None:
            raise VideoError("A Flow end frame requires a start frame")
        if start_frame is not None and images:
            raise VideoError(
                "Flow cannot combine a literal start frame with reference images in one request"
            )
        if end_frame is not None and images:
            raise VideoError(
                "Flow cannot combine first/last-frame generation with reference images"
            )

        self.preflight()
        self.check_credits(duration=duration, count=1)

        # Aspect ratio conversion
        aspect = "portrait" if aspect_ratio in {"9:16", "portrait"} else "landscape"

        start_media_id = None
        end_media_id = None
        ref_ids: list[str] = []
        has_fresh_uploads = False

        # Keep legacy direct calls deterministic: image_to_video treats its sole
        # image as the start frame. Story generation passes start_frame explicitly.
        if start_frame is not None:
            start_media_id, fresh = upload_media_file(self.base, start_frame, "start frame")
            has_fresh_uploads = has_fresh_uploads or fresh
        elif task == "image_to_video" and images:
            start_media_id, fresh = upload_media_file(self.base, images[0], "start frame")
            has_fresh_uploads = has_fresh_uploads or fresh
            images = images[1:]

        if end_frame is not None:
            end_media_id, fresh = upload_media_file(self.base, end_frame, "end frame")
            has_fresh_uploads = has_fresh_uploads or fresh

        # Upload reference images
        for idx, img_path in enumerate(images, 1):
            mid, fresh = upload_media_file(self.base, img_path, f"reference {idx}")
            ref_ids.append(mid)
            has_fresh_uploads = has_fresh_uploads or fresh

        # Upload edit video if any
        edit_media_id = None
        if videos:
            edit_media_id, fresh = upload_media_file(self.base, videos[0], "video for editing")
            has_fresh_uploads = has_fresh_uploads or fresh

        model_key = model or "omni_flash"
        model_override = VIDEO_MODEL_MAP.get(model_key.lower(), model_key)

        body: dict[str, Any] = {
            "prompt": prompt,
            "duration": duration,
            "aspect": aspect,
            "n": 1,
        }
        if model_override:
            body["video_model"] = model_override
        if start_media_id:
            body["start_media_id"] = start_media_id
        if end_media_id:
            body["end_media_id"] = end_media_id
        if ref_ids:
            body["ref_media_ids"] = ref_ids
        if edit_media_id:
            body["start_media_id"] = edit_media_id
            body["is_video"] = True

        if has_fresh_uploads:
            print("  Fresh media upload detected; waiting 5s for Google media indexing...")
            time.sleep(5.0)

        print(f"Submitting Flow video generation job ({duration}s, {aspect})...")
        res = None
        retry_delays = [3.0, 6.0, 10.0]
        max_attempts = len(retry_delays) + 1

        for attempt_idx in range(1, max_attempts + 1):
            try:
                res = _post(f"{self.base}/v1/videos/generations", body)
                break
            except urllib.error.HTTPError as exc:
                code = exc.code
                detail = _post_err(exc)
                if code == 402:
                    raise CreditError(f"Insufficient Flow credits: {detail}") from exc
                elif code == 503:
                    raise ProviderUnavailableError(f"No Chrome extension connected: {detail}") from exc
                elif code == 400 and attempt_idx <= len(retry_delays):
                    delay = retry_delays[attempt_idx - 1]
                    print(f"  Transient submission error ({detail}); waiting {delay}s for Google media indexing (attempt {attempt_idx}/{max_attempts})...")
                    time.sleep(delay)
                    continue
                elif code == 404:
                    # Invalidate local cache in case a media_id expired remotely
                    try:
                        cache_path = _get_cache_path()
                        if cache_path.is_file():
                            cache_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise VideoError(f"Flow media reference rejected (HTTP 404: {detail}). Cache cleared; retry to upload fresh assets.") from exc
                else:
                    raise VideoError(f"Flow generation submission failed (HTTP {code}): {detail}") from exc
            except Exception as exc:
                raise VideoError(f"Flow submission failed: {exc}") from exc

        if not res:
            raise VideoError("Flow generation submission failed after retries")

        job_id = res.get("job_id")
        status = res.get("status")
        if not job_id:
            raise VideoError(f"Flow returned response without job_id: {res}")

        # If immediately succeeded
        if status == "succeeded":
            items = res.get("data", [])
            return self._download_output(items, output)

        # Poll for completion
        return self._poll_and_download(job_id, output, timeout=poll_timeout)

    def _poll_and_download(self, job_id: str, output: Path, timeout: int = 300) -> int:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                job = _get(f"{self.base}/v1/videos/generations/{job_id}", timeout=10)
            except Exception as exc:
                print(f"Warning: Flow poll error: {exc}. Retrying...")
                time.sleep(POLL_INTERVAL)
                continue

            status = job.get("status")
            elapsed = time.time() - start_time
            print(f"\r  Flow generating... ({elapsed:.0f}s elapsed)", end="", flush=True)

            if status == "succeeded":
                print()
                items = job.get("data", [])
                return self._download_output(items, output)

            if status == "failed":
                print()
                err = job.get("error", {})
                detail = err.get("detail", str(err)) if isinstance(err, dict) else str(err)
                raise VideoError(f"Flow video generation failed: {detail}")

            time.sleep(POLL_INTERVAL)

        print()
        raise VideoError(f"Flow generation timed out after {timeout}s (job_id={job_id}).")

    def _download_output(self, items: list[dict[str, Any]], output: Path) -> int:
        if not items:
            raise VideoError("Flow generation succeeded but returned empty media items.")

        first_item = items[0]
        url = first_item.get("url")
        b64_data = first_item.get("b64_json")

        output.parent.mkdir(parents=True, exist_ok=True)

        if url:
            try:
                urllib.request.urlretrieve(url, output)
            except Exception as exc:
                raise VideoError(f"Failed to download video from {url}: {exc}") from exc
        elif b64_data:
            output.write_bytes(base64.b64decode(b64_data))
        else:
            raise VideoError(f"Flow media item has neither url nor b64_json: {first_item}")

        byte_length = output.stat().st_size
        return byte_length


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate video with Google Flow.")
    parser.add_argument("--prompt", "-p", required=True, help="Video prompt")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Destination .mp4 path")
    parser.add_argument(
        "--ref-file",
        type=Path,
        action="append",
        default=[],
        help="Reference image file; repeat for multiple references",
    )
    parser.add_argument("--start", type=Path, default=None, help="First frame image")
    parser.add_argument("--end", type=Path, default=None, help="Last frame image")
    parser.add_argument("--duration", "-d", type=int, choices=[4, 6, 8, 10], default=10)
    parser.add_argument("--aspect", choices=["landscape", "portrait", "16:9", "9:16"], default="landscape")
    parser.add_argument("--model", default="omni_flash", help="Video model (default: omni_flash)")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Flow local server host:port")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    provider = FlowProvider(host=args.host)
    print("Checking Flow server health & credits...")
    provider.preflight()
    byte_count = provider.generate_video(
        prompt=args.prompt,
        output=args.output,
        images=args.ref_file,
        start_frame=args.start,
        end_frame=args.end,
        duration=args.duration,
        aspect_ratio="9:16" if args.aspect in {"portrait", "9:16"} else "16:9",
        model=args.model,
    )
    print(f"Saved {byte_count:,} bytes to {args.output}")


if __name__ == "__main__":
    main()
