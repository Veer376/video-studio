from __future__ import annotations

import argparse
import base64
import io
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from types import SimpleNamespace

from PIL import Image


REFERENCE_MAX_DIMENSION = 511
MAX_REFERENCE_IMAGES = 4


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
    normalized = model.strip()
    if not normalized.startswith("@cf/") and "/" not in normalized and "flux" in normalized:
        return f"@cf/black-forest-labs/{normalized}"
    return normalized


def load_credentials() -> list[tuple[str, str]]:
    """Collect all configured Cloudflare account/token pairs."""
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def get(*keys: str) -> str:
        for key in keys:
            value = os.environ.get(key, "").strip().strip('"').strip("'")
            if value:
                return value
        return ""

    def add(account_id: str, token: str) -> None:
        pair = (account_id, token)
        if account_id and token and pair not in seen:
            pairs.append(pair)
            seen.add(pair)

    add(
        get("CLOUDFLARE_ACCOUNT_ID", "CLOURFLARE_ACCOUNT_ID"),
        get("CLOUDFLARE_API_TOKEN", "CLOURFLARE_API_TOKEN"),
    )
    index = 1
    while True:
        account_id = get(
            f"CLOUDFLARE_ACCOUNT_ID_{index}",
            f"CLOURFLARE_ACCOUNT_ID_{index}",
        )
        token = get(
            f"CLOUDFLARE_API_TOKEN_{index}",
            f"CLOURFLARE_API_TOKEN_{index}",
        )
        if not account_id and not token and index > 10:
            break
        add(
            account_id,
            token,
        )
        index += 1
    return pairs


def _is_valid_image(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def _build_multipart(
    fields: dict[str, str | int | float],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----story-video-{uuid.uuid4().hex}"
    body: list[bytes] = []
    for key, value in fields.items():
        body.extend(
            [
                f"--{boundary}".encode(),
                f'Content-Disposition: form-data; name="{key}"'.encode(),
                b"",
                str(value).encode(),
            ]
        )
    for key, (filename, content, content_type) in files.items():
        body.extend(
            [
                f"--{boundary}".encode(),
                f'Content-Disposition: form-data; name="{key}"; filename="{filename}"'.encode(),
                f"Content-Type: {content_type}".encode(),
                b"",
                content,
            ]
        )
    body.extend([f"--{boundary}--".encode(), b""])
    return b"\r\n".join(body), f"multipart/form-data; boundary={boundary}"


def _prepare_reference(path: Path) -> bytes:
    with Image.open(path) as image:
        image.load()
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        image.thumbnail(
            (REFERENCE_MAX_DIMENSION, REFERENCE_MAX_DIMENSION),
            Image.Resampling.LANCZOS,
        )
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()


def _reference_instruction(references: list[object]) -> str:
    mappings = "; ".join(
        f"input image {index} is {reference.role}"
        for index, reference in enumerate(references)
    )
    instruction = (
        f"Reference mapping: {mappings}. Preserve the referenced character identities, "
        "clothing, props, environment, and art style where applicable. Use a previous-scene "
        "reference only for continuity. Follow the current scene description for action, "
        "expression, camera, and composition."
    )
    if any(reference.role.startswith("source identity of ") for reference in references):
        instruction += (
            " Treat a source identity reference as identity evidence only; do not preserve "
            "its medium, aspect ratio, background, lighting, or composition."
        )
    return instruction


def _save_response(response_data: bytes, content_type: str, out_path: Path) -> None:
    image_bytes = response_data
    if "application/json" in content_type:
        data = json.loads(response_data.decode("utf-8"))
        try:
            image_bytes = base64.b64decode(data["result"]["image"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Unexpected Cloudflare JSON response structure: {data}") from exc
    out_path.parent.mkdir(parents=True, exist_ok=True)
    partial = out_path.with_suffix(f"{out_path.suffix}.partial")
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()
            image.save(partial, format="PNG")
        partial.replace(out_path)
    finally:
        partial.unlink(missing_ok=True)


def generate_image(
    *,
    credentials: list[tuple[str, str]],
    model: str,
    prompt: str,
    width: int,
    height: int,
    out_path: Path,
    reference_images: list[object] | None = None,
) -> None:
    if not credentials:
        raise RuntimeError("No Cloudflare credentials provided")
    references = list(reference_images or [])
    if len(references) > MAX_REFERENCE_IMAGES:
        raise ValueError(f"Cloudflare supports at most {MAX_REFERENCE_IMAGES} reference images")
    for reference in references:
        if not _is_valid_image(reference.path):
            raise ValueError(f"reference image is missing or invalid: {reference.path}")

    is_flux_2 = "flux-2-" in model
    if references and not is_flux_2:
        raise ValueError(f"reference images are not configured for model {model}")
    if is_flux_2:
        fields: dict[str, str | int | float] = {
            "prompt": prompt,
            "width": width,
            "height": height,
        }
        files: dict[str, tuple[str, bytes, str]] = {}
        if references:
            fields["prompt"] = f"{_reference_instruction(references)} {prompt}"
            for index, reference in enumerate(references):
                files[f"input_image_{index}"] = (
                    f"reference-{index}.png",
                    _prepare_reference(reference.path),
                    "image/png",
                )
        data_bytes, content_type = _build_multipart(fields, files)
    else:
        data_bytes = json.dumps(
            {"prompt": prompt, "width": width, "height": height}
        ).encode()
        content_type = "application/json"

    try:
        context = ssl._create_unverified_context()
    except Exception:
        context = ssl.create_default_context()
    max_attempts = len(credentials) * 3
    for attempt in range(1, max_attempts + 1):
        credential_index = (attempt - 1) % len(credentials)
        account_id, api_token = credentials[credential_index]
        request = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
            data=data_bytes,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": content_type,
                "User-Agent": "story-video-maker/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120, context=context) as response:
                _save_response(
                    response.read(),
                    response.headers.get("Content-Type", ""),
                    out_path,
                )
                print(f"✓ Image saved: {out_path.name} (model: {model})")
                return
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            quota_error = exc.code == 429 or any(
                marker in detail
                for marker in ("4006", "daily free allocation", "used up your daily free allocation")
            )
            if quota_error and len(credentials) > 1:
                next_index = (credential_index + 1) % len(credentials)
                print(
                    f"  Warning: Cloudflare HTTP {exc.code} quota limit on account "
                    f"key[{credential_index + 1}/{len(credentials)}] ({account_id[:8]}...). "
                    f"Rotating to key[{next_index + 1}]...",
                    file=sys.stderr,
                )
                time.sleep(1.0)
                continue
            if exc.code in (429, 500, 503, 504) and attempt < max_attempts:
                wait = 3.0 * attempt
                print(
                    f"  Cloudflare HTTP {exc.code} (attempt {attempt}/{max_attempts}). "
                    f"Retrying in {wait}s...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            raise RuntimeError(f"Cloudflare HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < max_attempts:
                print(
                    f"  Cloudflare network error (attempt {attempt}/{max_attempts}). Retrying...",
                    file=sys.stderr,
                )
                time.sleep(3.0)
                continue
            raise RuntimeError(f"Cloudflare network error: {exc.reason}") from exc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate one image with Cloudflare Workers AI")
    parser.add_argument("--model", required=True, help="Cloudflare model ID")
    parser.add_argument("--prompt", required=True, help="Image-generation prompt")
    parser.add_argument("--output", required=True, type=Path, help="Output PNG path")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--force", action="store_true", help="Allow replacing an existing output")
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        metavar="ROLE=PATH",
        help="Ordered reference image mapping; repeat for multiple references",
    )
    args = parser.parse_args(argv)
    if args.width < 1 or args.height < 1:
        parser.error("--width and --height must be positive")
    try:
        references = _parse_references(args.reference)
    except ValueError as exc:
        parser.error(str(exc))
    if args.output.exists() and not args.force:
        parser.error(f"output already exists: {args.output}; use --force to replace it")
    invalid = [str(reference.path) for reference in references if not _is_valid_image(reference.path)]
    if invalid:
        parser.error(f"reference image is missing or invalid: {', '.join(invalid)}")
    _load_env()
    credentials = load_credentials()
    if not credentials:
        parser.error("Cloudflare credentials were not found")
    generate_image(
        credentials=credentials,
        model=normalize_model(args.model),
        prompt=args.prompt,
        width=args.width,
        height=args.height,
        out_path=args.output.expanduser(),
        reference_images=references,
    )


if __name__ == "__main__":
    main()
