"""Google Flow image-generation transport adapter.

This provider talks directly to the local ``flow-agent`` HTTP backend used by the
``/flow`` skill.  The free ``lite`` model maps to Flow's ``harbor_seal`` image
model and supports ordered reference images for character and scene continuity.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable

from PIL import Image


DEFAULT_BASE_URL = "http://127.0.0.1:8001"
MAX_REFERENCE_IMAGES = 4

MODEL_ALIASES = {
    "lite": "harbor_seal",
    "harbor_seal": "harbor_seal",
    "standard": "narwhal",
    "narwhal": "narwhal",
    "pro": "gem_pix_2",
    "gem_pix_2": "gem_pix_2",
    "nano_banana_2": "gem_pix_2",
}
SUPPORTED_MODELS = {"harbor_seal", "narwhal", "gem_pix_2"}
ASPECT_TO_SIZE = {
    "1:1": "1024x1024",
    "16:9": "1792x1024",
    "9:16": "1024x1792",
    "4:3": "1024x768",
    "3:4": "768x1024",
}

# Uploading the same canonical character for every scene is wasteful.  Cache
# Flow media IDs only for the lifetime of this process; a backend restart cannot
# leave a stale cache behind on the next story-video invocation.
_REFERENCE_MEDIA_CACHE: dict[tuple[str, int, int], str] = {}
_REFERENCE_MEDIA_LOCK = threading.Lock()


def _load_env() -> None:
    env_path = Path.home() / ".config/projects/.env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _parse_references(values: list[str]) -> list[SimpleNamespace]:
    references: list[SimpleNamespace] = []
    for value in values:
        role, separator, path = value.partition("=")
        if not separator or not role.strip() or not path.strip():
            raise ValueError("--reference must use ROLE=PATH")
        references.append(SimpleNamespace(role=role.strip(), path=Path(path).expanduser()))
    return references


def normalize_model(model: str) -> str:
    normalized = MODEL_ALIASES.get(model.strip().lower(), model.strip().lower())
    if normalized not in SUPPORTED_MODELS:
        choices = ", ".join(sorted(MODEL_ALIASES))
        raise ValueError(f"Unsupported Flow image model {model!r}; choose one of: {choices}")
    return normalized


def resolve_base_url() -> str:
    return (os.environ.get("FLOW_AGENT_URL") or DEFAULT_BASE_URL).rstrip("/")


def _json_request(
    url: str,
    *,
    body: dict | None = None,
    timeout: float = 30,
) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _http_error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8", errors="replace"))
        return str(payload.get("detail") or payload)
    except Exception:
        return str(exc)


def require_ready(base_url: str | None = None) -> dict:
    """Validate that Flow backend, Chrome extension, and captured key are ready."""
    base = (base_url or resolve_base_url()).rstrip("/")
    try:
        health = _json_request(f"{base}/health", timeout=8)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            "Flow Agent backend is not reachable. Start it with ~/.local/bin/flow"
        ) from exc
    if not health.get("extension_connected", False):
        raise RuntimeError(
            "Flow Agent Chrome extension is not connected; open/refresh Google Flow with the extension enabled"
        )
    if not health.get("has_flow_key", False):
        raise RuntimeError(
            "Flow key is not captured; open Google Flow in Chrome while signed in and refresh the page"
        )
    return health


def _is_valid_image(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def _reference_instruction(references: Iterable[object]) -> str:
    references = list(references)
    mappings = "; ".join(
        f"reference image {index} is {reference.role}"
        for index, reference in enumerate(references)
    )
    instruction = (
        f"Reference mapping: {mappings}. Preserve referenced identities, clothing, props, "
        "environment, lighting logic, and art style where applicable. A previous-scene "
        "reference exists for continuity: preserve everything that the current prompt does "
        "not explicitly change. The current prompt controls only the requested action, "
        "expression, gesture, camera adjustment, and composition delta."
    )
    if any(reference.role.startswith("source identity of ") for reference in references):
        instruction += (
            " Treat a source identity reference as identity evidence only; do not preserve "
            "its original medium, aspect ratio, background, lighting, or composition."
        )
    return instruction


def _reference_png_data_uri(path: Path) -> str:
    with Image.open(path) as image:
        image.load()
        converted = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        output = io.BytesIO()
        converted.save(output, format="PNG", optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _reference_cache_key(path: Path) -> tuple[str, int, int]:
    resolved = path.expanduser().resolve()
    stat = resolved.stat()
    return (str(resolved), stat.st_mtime_ns, stat.st_size)


def _media_id_exists(base_url: str, media_id: str) -> bool:
    try:
        history = _json_request(f"{base_url}/v1/history", timeout=10).get("history") or []
    except Exception:
        # History verification is a safety enhancement, not a reason to make a healthy
        # generation fail merely because the history endpoint had a transient problem.
        return True
    return any(str(item.get("media_id") or "") == media_id for item in history)


def _invalidate_reference_cache(path: Path) -> None:
    resolved = str(path.expanduser().resolve())
    with _REFERENCE_MEDIA_LOCK:
        stale = [key for key in _REFERENCE_MEDIA_CACHE if key[0] == resolved]
        for key in stale:
            _REFERENCE_MEDIA_CACHE.pop(key, None)


def upload_reference(
    path: Path,
    *,
    base_url: str | None = None,
    force_upload: bool = False,
) -> str:
    """Upload a local reference image to Flow with verified in-process reuse."""
    path = path.expanduser()
    if not _is_valid_image(path):
        raise ValueError(f"reference image is missing or invalid: {path}")
    key = _reference_cache_key(path)
    base = (base_url or resolve_base_url()).rstrip("/")

    if not force_upload:
        with _REFERENCE_MEDIA_LOCK:
            cached = _REFERENCE_MEDIA_CACHE.get(key)
        if cached and _media_id_exists(base, cached):
            return cached
        if cached:
            _invalidate_reference_cache(path)

    try:
        response = _json_request(
            f"{base}/v1/upload",
            body={"image_base64": _reference_png_data_uri(path)},
            timeout=60,
        )
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Flow reference upload failed: {_http_error_detail(exc)}") from exc
    media_id = str(response.get("media_id") or "").strip()
    if not media_id:
        raise RuntimeError(f"Flow reference upload returned no media_id: {response}")
    with _REFERENCE_MEDIA_LOCK:
        _REFERENCE_MEDIA_CACHE[key] = media_id
    return media_id


def _download_image_as_png(url: str, out_path: Path) -> None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "story-video-maker/0.1"})
        with urllib.request.urlopen(request, timeout=120) as response:
            image_bytes = response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Flow image download failed: {exc}") from exc

    out_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = out_path.with_name(f".{out_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()
            image.convert("RGB").save(temporary, format="PNG")
        temporary.replace(out_path)
    finally:
        temporary.unlink(missing_ok=True)


def generate_image(
    *,
    model: str,
    prompt: str,
    aspect_ratio: str,
    out_path: Path,
    reference_images: list[object] | None = None,
    base_url: str | None = None,
) -> None:
    """Generate one image through Flow and save it atomically as PNG."""
    normalized_model = normalize_model(model)
    if aspect_ratio not in ASPECT_TO_SIZE:
        choices = ", ".join(ASPECT_TO_SIZE)
        raise ValueError(f"Unsupported Flow aspect ratio {aspect_ratio!r}; choose one of: {choices}")
    references = list(reference_images or [])
    if len(references) > MAX_REFERENCE_IMAGES:
        raise ValueError(f"Flow provider supports at most {MAX_REFERENCE_IMAGES} reference images")
    for reference in references:
        if not _is_valid_image(reference.path):
            raise ValueError(f"reference image is missing or invalid: {reference.path}")

    base = (base_url or resolve_base_url()).rstrip("/")

    def prepare_reference_ids(*, force_upload: bool = False) -> list[str]:
        return [
            upload_reference(
                reference.path,
                base_url=base,
                force_upload=force_upload,
            )
            for reference in references
        ]

    ref_media_ids = prepare_reference_ids()
    effective_prompt = (
        f"{_reference_instruction(references)} {prompt}" if references else prompt
    )
    body: dict[str, object] = {
        "prompt": effective_prompt,
        "model": normalized_model,
        "n": 1,
        "size": ASPECT_TO_SIZE[aspect_ratio],
    }
    if ref_media_ids:
        body["ref_media_ids"] = ref_media_ids

    max_attempts = 3
    response: dict | None = None
    reference_recovery_used = False
    for attempt in range(1, max_attempts + 1):
        try:
            response = _json_request(
                f"{base}/v1/images/generations",
                body=body,
                timeout=180,
            )
            break
        except urllib.error.HTTPError as exc:
            detail = _http_error_detail(exc)
            missing_reference = (
                exc.code == 404
                and references
                and "Media not found in history.json" in detail
            )
            if missing_reference and not reference_recovery_used:
                print("  ⚠ Flow lost a cached reference media ID; re-uploading references once...")
                for reference in references:
                    _invalidate_reference_cache(reference.path)
                body["ref_media_ids"] = prepare_reference_ids(force_upload=True)
                reference_recovery_used = True
                continue
            if exc.code in (429, 500, 502, 503, 504) and attempt < max_attempts:
                wait = 2.0 * attempt
                print(
                    f"  ⚠ Flow HTTP {exc.code}, retrying in {wait:.0f}s "
                    f"(attempt {attempt}/{max_attempts})..."
                )
                time.sleep(wait)
                continue
            if exc.code == 402:
                raise RuntimeError(
                    f"Flow model {normalized_model} requires unavailable credits: {detail}"
                ) from exc
            raise RuntimeError(f"Flow generation failed (HTTP {exc.code}): {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt < max_attempts:
                time.sleep(2.0 * attempt)
                continue
            raise RuntimeError(f"Flow backend/network error: {exc}") from exc

    if response is None:
        raise RuntimeError("Flow generation failed without a response")
    items = response.get("data") or []
    if not isinstance(items, list) or not items:
        raise RuntimeError(f"Flow returned no images: {response}")
    url = str(items[0].get("url") or "").strip()
    if not url:
        raise RuntimeError(f"Flow returned an image without a URL: {response}")
    _download_image_as_png(url, out_path)
    print(f"✓ Image saved: {out_path.name} (Flow model: {normalized_model})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate one image with Google Flow")
    parser.add_argument(
        "--model",
        default="pro",
        help="Flow image model: lite/free, standard, pro, or backend model ID [default: pro]",
    )
    parser.add_argument("--prompt", required=True, help="Image-generation prompt")
    parser.add_argument("--output", required=True, type=Path, help="Output PNG path")
    parser.add_argument(
        "--aspect-ratio",
        default="1:1",
        choices=tuple(ASPECT_TO_SIZE),
        help="Output aspect ratio",
    )
    parser.add_argument("--force", action="store_true", help="Allow replacing an existing output")
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        metavar="ROLE=PATH",
        help="Ordered reference image mapping; repeat for multiple references",
    )
    args = parser.parse_args(argv)
    try:
        references = _parse_references(args.reference)
        model = normalize_model(args.model)
    except ValueError as exc:
        parser.error(str(exc))
    if args.output.exists() and not args.force:
        parser.error(f"output already exists: {args.output}; use --force to replace it")
    invalid = [str(reference.path) for reference in references if not _is_valid_image(reference.path)]
    if invalid:
        parser.error(f"reference image is missing or invalid: {', '.join(invalid)}")

    _load_env()
    try:
        require_ready()
        generate_image(
            model=model,
            prompt=args.prompt,
            aspect_ratio=args.aspect_ratio,
            out_path=args.output.expanduser(),
            reference_images=references,
        )
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
