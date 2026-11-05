"""Google Vertex image-generation transport adapter."""

from __future__ import annotations

import argparse
import io
import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable

from PIL import Image


MODEL_ALIASES = {
    "nano-banana-2": "gemini-3.1-flash-image",
    "nano-banana-pro": "gemini-3-pro-image",
    "nano-banana": "gemini-2.5-flash-image",
}
SUPPORTED_MODELS = {
    "gemini-3.1-flash-image",
    "gemini-3-pro-image",
    "gemini-2.5-flash-image",
}


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
    normalized = MODEL_ALIASES.get(model.strip(), model.strip())
    if normalized not in SUPPORTED_MODELS:
        choices = ", ".join(sorted(SUPPORTED_MODELS))
        raise ValueError(f"Unsupported Google image model {model!r}; choose one of: {choices}")
    return normalized


def create_client():
    try:
        import google.auth
        from google import genai
    except ImportError as exc:
        raise RuntimeError("Google image generation requires the google-genai package") from exc

    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT_ID")
    if not project:
        _, project = google.auth.default()
    if not project:
        raise RuntimeError(
            "Google Cloud project is missing; set GOOGLE_CLOUD_PROJECT or configure ADC"
        )
    return genai.Client(vertexai=True, project=project, location="global")


def _reference_instruction(references: Iterable[object]) -> str:
    references = list(references)
    mappings = "; ".join(
        f"input image {index} is {reference.role}"
        for index, reference in enumerate(references)
    )
    instruction = (
        f"Reference mapping: {mappings}. Preserve referenced identities, clothing, props, "
        "environment, and art style where applicable. A previous-scene image provides "
        "continuity only. The current prompt controls action, expression, camera, and composition."
    )
    if any(reference.role.startswith("source identity of ") for reference in references):
        instruction += (
            " Treat a source identity reference as identity evidence only; do not preserve "
            "its medium, aspect ratio, background, lighting, or composition."
        )
    return instruction


def _png_bytes(path: Path) -> bytes:
    with Image.open(path) as image:
        image.load()
        converted = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        output = io.BytesIO()
        converted.save(output, format="PNG")
        return output.getvalue()


def _final_image_bytes(response: object) -> bytes:
    candidates = getattr(response, "candidates", None) or []
    for candidate in reversed(candidates):
        content = getattr(candidate, "content", None)
        for part in reversed(getattr(content, "parts", None) or []):
            if getattr(part, "thought", False):
                continue
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None)
            if data:
                return data
    raise RuntimeError("Google returned no final image")


def generate_image(
    *,
    client: object,
    model: str,
    prompt: str,
    aspect_ratio: str,
    out_path: Path,
    reference_images: list[object] | None = None,
) -> None:
    from google.genai import types

    normalized_model = normalize_model(model)
    references = list(reference_images or [])
    parts = [
        types.Part.from_bytes(data=_png_bytes(reference.path), mime_type="image/png")
        for reference in references
    ]
    effective_prompt = (
        f"{_reference_instruction(references)} {prompt}" if references else prompt
    )
    parts.append(types.Part.from_text(text=effective_prompt))

    image_config_args: dict[str, str] = {"aspect_ratio": aspect_ratio}
    if normalized_model != "gemini-2.5-flash-image":
        image_config_args["image_size"] = "2K"
    import time

    config = types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(**image_config_args),
    )
    max_retries = 12
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=normalized_model,
                contents=[types.Content(role="user", parts=parts)],
                config=config,
            )
            break
        except Exception as exc:
            err_str = str(exc)
            if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt < max_retries - 1:
                wait_sec = (attempt + 1) * 15
                print(f"  ⚠ Google 429 quota hit, retrying in {wait_sec}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_sec)
                continue
            raise
    image_bytes = _final_image_bytes(response)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = out_path.with_name(f".{out_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()
            image.save(temporary, format="PNG")
        temporary.replace(out_path)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"✓ Image saved: {out_path.name} (model: {normalized_model})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate one image with Google Vertex AI")
    parser.add_argument("--model", required=True, help="Google image model ID or alias")
    parser.add_argument("--prompt", required=True, help="Image-generation prompt")
    parser.add_argument("--output", required=True, type=Path, help="Output PNG path")
    parser.add_argument("--aspect-ratio", default="1:1", help="Output aspect ratio, such as 9:16 or 16:9")
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
    for reference in references:
        try:
            with Image.open(reference.path) as image:
                image.verify()
        except (OSError, ValueError):
            parser.error(f"reference image is missing or invalid: {reference.path}")
    _load_env()
    generate_image(
        client=create_client(),
        model=model,
        prompt=args.prompt,
        aspect_ratio=args.aspect_ratio,
        out_path=args.output.expanduser(),
        reference_images=references,
    )


if __name__ == "__main__":
    main()
