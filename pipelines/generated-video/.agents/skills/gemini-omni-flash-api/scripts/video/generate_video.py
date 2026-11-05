#!/usr/bin/env python3
"""Standalone Gemini Omni 1.1 Flash video generation/editing client.

This file deliberately knows nothing about Video Studio scenes, characters,
locations, reviews, or project registries. It exposes Gemini Omni's useful
video surface directly and adds only one convenience: media references can be
addressed either with native Omni tokens (for example ``<IMAGE_REF_0>``) or
with ``@name`` handles derived from the supplied filename/alias.

Examples:

    # Text to video.
    python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
      --prompt 'A marble rolls through a chain reaction track.' \
      --output marble.mp4

    # @handles. The filename stem is the default handle.
    python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
      --prompt '@dog walks through @kitchen.' \
      --image-ref dog.png \
      --image-ref kitchen.png \
      --output scene.mp4

    # Explicit aliases and native Omni syntax can be mixed.
    python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
      --prompt '@dog walks toward <IMAGE_REF_1>.' \
      --image-ref dog=assets/hero.png \
      --image-ref doorway=assets/door.png \
      --output scene.mp4

    # Literal start/end frames plus a reference character.
    python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
      --prompt '<FIRST_FRAME> @dog crosses the room and settles into <LAST_FRAME>.' \
      --first-frame start.png \
      --last-frame end.png \
      --image-ref dog.png \
      --output scene.mp4

    # Uploaded-video edit.
    python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
      --prompt 'Change only the umbrella to matte black. Keep everything else the same.' \
      --video input.mp4 \
      --task edit \
      --output edit.mp4

    # Stateful follow-up edit/extension.
    python .agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py \
      --prompt 'Continue the scene.' \
      --previous-interaction-id v1_... \
      --task extend \
      --duration 10 \
      --output continued.mp4 \
      --json

Use ``--capabilities`` for a machine-readable contract intended for agents.
Use ``--dry-run`` to validate/bind a request without calling Google.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


# This project has verified paid Vertex/ADC access to the Cloud preview model.
# The stable Developer API model remains available via --model when its quota is
# enabled for the configured Gemini API key.
DEFAULT_MODEL = "gemini-omni-1.1-flash"
DEFAULT_SHARED_ENV = Path.home() / ".config/projects/.env"

TASKS = (
    "text_to_video",
    "image_to_video",
    "reference_to_video",
    "edit",
    "extend",
)
ASPECT_RATIOS = ("16:9", "9:16")
RESOLUTIONS = ("360p", "720p", "1080p", "4k")
DELIVERY_MODES = ("auto", "inline", "uri")

IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/webm",
    "video/x-msvideo",
    "video/ogg",
}

HANDLE_RE = re.compile(
    r"(?<![A-Za-z0-9_-])@([A-Za-z0-9][A-Za-z0-9_-]*)(?![A-Za-z0-9_-])"
)
IMAGE_TOKEN_RE = re.compile(r"<IMAGE_REF_(\d+)>")
VIDEO_TOKEN_RE = re.compile(r"<VIDEO_REF_(\d+)>")
ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class OmniVideoError(RuntimeError):
    """Base error for this standalone client."""


class ConfigError(OmniVideoError):
    """Raised before making a paid API request."""


class ApiError(OmniVideoError):
    """Raised when Google does not return a usable video result."""


@dataclass(frozen=True)
class Reference:
    alias: str
    path: Path
    kind: str  # image | video


@dataclass(frozen=True)
class ClientInfo:
    client: Any
    backend: str  # vertex | developer
    label: str


@dataclass(frozen=True)
class CompiledRequest:
    prompt: str
    image_refs: tuple[Reference, ...]
    video_refs: tuple[Reference, ...]
    images_in_order: tuple[Path, ...]
    videos_in_order: tuple[Path, ...]
    unused_aliases: tuple[str, ...]


@dataclass(frozen=True)
class Result:
    interaction_id: str | None
    previous_interaction_id: str | None
    model: str
    backend: str
    operation: str | None
    task: str | None
    store: bool
    output_path: str
    output_uri: str | None
    output_mime_type: str | None
    requested_duration_seconds: int | None
    state_total_duration_seconds: float | None
    compiled_prompt: str
    warnings: tuple[str, ...]


def _load_shared_env() -> None:
    configured = os.environ.get("STUDIO_ENV_FILE")
    if not configured:
        return
    path = Path(configured).expanduser()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _developer_api_key() -> str | None:
    direct = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if direct:
        return direct
    numbered: list[tuple[int, str]] = []
    for key, value in os.environ.items():
        match = re.fullmatch(r"GEMINI_API_KEY_(\d+)", key)
        if match and value:
            numbered.append((int(match.group(1)), value))
    if numbered:
        numbered.sort(key=lambda item: item[0])
        return numbered[0][1]
    return None


def create_client(model: str = DEFAULT_MODEL) -> ClientInfo:
    """Use existing local Google authentication; expose no auth CLI."""
    try:
        from google import genai
    except ImportError as exc:
        raise ConfigError(
            "google-genai is unavailable. Run the project's dependency sync first."
        ) from exc

    _load_shared_env()
    api_key = _developer_api_key()

    # The stable Gemini API model uses the Developer API model ID. Google Cloud's
    # Gemini Enterprise Agent Platform exposes separate preview model IDs such as
    # `gemini-omni-1.1-flash-preview`, which must route through Vertex/ADC.
    is_vertex_omni_preview = model in {
        "gemini-omni-1.1-flash-preview",
        "gemini-omni-flash-preview",
    }
    if model.startswith("gemini-omni-") and not is_vertex_omni_preview and api_key:
        return ClientInfo(
            client=genai.Client(api_key=api_key),
            backend="developer",
            label="Gemini Developer API (existing local credentials)",
        )

    adc_project = None
    try:
        import google.auth

        _, adc_project = google.auth.default()
    except Exception:
        adc_project = None

    # For the Enterprise Agent Platform Omni preview, the active ADC project is
    # the authoritative Cloud project. A shared GCP_PROJECT_ID may belong to a
    # different Google workflow (and on this workstation is not billing-enabled
    # for Agent Platform), so do not let it shadow the authenticated ADC project.
    if is_vertex_omni_preview and adc_project:
        cloud_project = adc_project
    else:
        cloud_project = (
            os.getenv("GCP_PROJECT_ID")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or adc_project
        )

    if cloud_project:
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
        return ClientInfo(
            client=genai.Client(
                vertexai=True,
                project=cloud_project,
                location=location,
            ),
            backend="vertex",
            label=f"Vertex AI ADC project {cloud_project} ({location})",
        )

    if api_key:
        return ClientInfo(
            client=genai.Client(api_key=api_key),
            backend="developer",
            label="Gemini Developer API (existing local credentials)",
        )

    raise ConfigError(
        "Google authentication was not found. Expected existing ADC/project auth "
        "or Gemini Developer credentials in the environment/shared credential file."
    )


def _mime_type(path: Path, allowed: set[str]) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    if path.suffix.lower() == ".mov":
        mime_type = "video/quicktime"
    if mime_type not in allowed:
        raise ConfigError(
            f"Unsupported media type for {path}: {mime_type or 'unknown'}"
        )
    return mime_type


def _resolve_file(path: Path, *, kind: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ConfigError(f"{kind} does not exist: {resolved}")
    return resolved


def _parse_references(values: Sequence[str], *, kind: str) -> list[Reference]:
    refs: list[Reference] = []
    for raw in values:
        if "=" in raw:
            alias, raw_path = raw.split("=", 1)
            alias = alias.strip()
            raw_path = raw_path.strip()
        else:
            raw_path = raw
            alias = Path(raw_path).stem

        if not alias or not ALIAS_RE.fullmatch(alias):
            raise ConfigError(
                f"Invalid reference alias {alias!r}. Use letters/numbers plus _ - only."
            )
        path = _resolve_file(Path(raw_path), kind=f"{kind} reference")
        _mime_type(path, IMAGE_MIME_TYPES if kind == "image" else VIDEO_MIME_TYPES)
        refs.append(Reference(alias=alias, path=path, kind=kind))

    aliases = [ref.alias for ref in refs]
    duplicates = sorted({alias for alias in aliases if aliases.count(alias) > 1})
    if duplicates:
        raise ConfigError(
            "Duplicate reference aliases: " + ", ".join(f"@{x}" for x in duplicates)
        )
    return refs


def _validate_cross_kind_aliases(
    image_refs: Sequence[Reference], video_refs: Sequence[Reference]
) -> None:
    image_aliases = {ref.alias for ref in image_refs}
    video_aliases = {ref.alias for ref in video_refs}
    overlap = sorted(image_aliases & video_aliases)
    if overlap:
        raise ConfigError(
            "A handle cannot name both an image and video reference: "
            + ", ".join(f"@{x}" for x in overlap)
        )


def _read_prompt(prompt: str | None, prompt_file: Path | None) -> str:
    if prompt is not None and prompt_file is not None:
        raise ConfigError("Use either --prompt or --prompt-file, not both.")
    if prompt_file is not None:
        path = _resolve_file(prompt_file, kind="prompt file")
        prompt = path.read_text(encoding="utf-8")
    if not prompt or not prompt.strip():
        raise ConfigError("A non-empty --prompt or --prompt-file is required.")
    return prompt.strip()


def _replace_handles(
    prompt: str,
    image_refs: Sequence[Reference],
    video_refs: Sequence[Reference],
) -> str:
    mapping: dict[str, str] = {}
    mapping.update(
        {ref.alias: f"<IMAGE_REF_{idx}>" for idx, ref in enumerate(image_refs)}
    )
    mapping.update(
        {ref.alias: f"<VIDEO_REF_{idx}>" for idx, ref in enumerate(video_refs)}
    )
    unresolved: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        alias = match.group(1)
        token = mapping.get(alias)
        if token is None:
            unresolved.add(alias)
            return match.group(0)
        return token

    rewritten = HANDLE_RE.sub(replace, prompt)
    if unresolved:
        raise ConfigError(
            "Unresolved @handles: "
            + ", ".join(f"@{alias}" for alias in sorted(unresolved))
        )
    return rewritten


def _validate_reference_tokens(
    prompt: str,
    image_refs: Sequence[Reference],
    video_refs: Sequence[Reference],
) -> None:
    image_indices = [int(match.group(1)) for match in IMAGE_TOKEN_RE.finditer(prompt)]
    video_indices = [int(match.group(1)) for match in VIDEO_TOKEN_RE.finditer(prompt)]

    if image_indices and max(image_indices) >= len(image_refs):
        raise ConfigError(
            f"Prompt uses <IMAGE_REF_{max(image_indices)}> but only "
            f"{len(image_refs)} --image-ref value(s) were supplied."
        )
    if video_indices and max(video_indices) >= len(video_refs):
        raise ConfigError(
            f"Prompt uses <VIDEO_REF_{max(video_indices)}> but only "
            f"{len(video_refs)} --video-ref value(s) were supplied."
        )


def _unused_aliases(
    prompt: str,
    image_refs: Sequence[Reference],
    video_refs: Sequence[Reference],
) -> tuple[str, ...]:
    used_image_indices = {int(m.group(1)) for m in IMAGE_TOKEN_RE.finditer(prompt)}
    used_video_indices = {int(m.group(1)) for m in VIDEO_TOKEN_RE.finditer(prompt)}
    unused: list[str] = []
    for idx, ref in enumerate(image_refs):
        if idx not in used_image_indices:
            unused.append(ref.alias)
    for idx, ref in enumerate(video_refs):
        if idx not in used_video_indices:
            unused.append(ref.alias)
    return tuple(unused)


def compile_request(
    *,
    prompt: str,
    first_frame: Path | None,
    last_frame: Path | None,
    image_refs: Sequence[Reference],
    source_video: Path | None,
    video_refs: Sequence[Reference],
) -> CompiledRequest:
    """Compile friendly @handles into Google's positional Omni binding syntax."""
    prompt = _replace_handles(prompt, image_refs, video_refs)

    if first_frame is not None and "<FIRST_FRAME>" not in prompt:
        prompt = f"<FIRST_FRAME> {prompt}"
    if last_frame is not None and "<LAST_FRAME>" not in prompt:
        prompt = f"<LAST_FRAME> {prompt}"

    if "<FIRST_FRAME>" in prompt and first_frame is None:
        raise ConfigError("Prompt uses <FIRST_FRAME> but --first-frame is missing.")
    if "<LAST_FRAME>" in prompt and last_frame is None:
        raise ConfigError("Prompt uses <LAST_FRAME> but --last-frame is missing.")

    _validate_reference_tokens(prompt, image_refs, video_refs)

    images: list[Path] = []
    videos: list[Path] = []
    source_bindings: list[str] = []
    reference_bindings: list[str] = []

    first_image_number: int | None = None
    if first_frame is not None:
        first_image_number = len(images) + 1
        images.append(first_frame)
        source_bindings.append(f"<FIRST_FRAME>@Image{first_image_number}")

    if last_frame is not None:
        if first_frame is not None and last_frame == first_frame:
            assert first_image_number is not None
            last_image_number = first_image_number
        else:
            last_image_number = len(images) + 1
            images.append(last_frame)
        source_bindings.append(f"<LAST_FRAME>@Image{last_image_number}")

    for idx, ref in enumerate(image_refs):
        image_number = len(images) + 1
        images.append(ref.path)
        reference_bindings.append(f"<IMAGE_REF_{idx}>@Image{image_number}")

    if source_video is not None:
        video_number = len(videos) + 1
        videos.append(source_video)
        source_bindings.append(f"<VIDEO_0>@Video{video_number}")

    for idx, ref in enumerate(video_refs):
        video_number = len(videos) + 1
        videos.append(ref.path)
        reference_bindings.append(f"<VIDEO_REF_{idx}>@Video{video_number}")

    prefix: list[str] = []
    if source_bindings:
        prefix.append(f"[# Sources {' '.join(source_bindings)}]")
    if reference_bindings:
        prefix.append(f"[# References {' '.join(reference_bindings)}]")

    compiled_prompt = "\n".join([*prefix, prompt]) if prefix else prompt
    return CompiledRequest(
        prompt=compiled_prompt,
        image_refs=tuple(image_refs),
        video_refs=tuple(video_refs),
        images_in_order=tuple(images),
        videos_in_order=tuple(videos),
        unused_aliases=_unused_aliases(prompt, image_refs, video_refs),
    )


def _media_input(
    path: Path, *, kind: str, strip_audio: bool = False
) -> dict[str, str]:
    input_path = path
    temp_path: Path | None = None
    if strip_audio and kind == "video":
        fd, raw_temp = tempfile.mkstemp(suffix=path.suffix or ".mp4")
        os.close(fd)
        temp_path = Path(raw_temp)
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(path),
                "-c:v",
                "copy",
                "-an",
                str(temp_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            temp_path.unlink(missing_ok=True)
            raise ConfigError(
                f"ffmpeg could not strip audio from {path}: {proc.stderr.strip()}"
            )
        input_path = temp_path

    mime_type = _mime_type(
        input_path, IMAGE_MIME_TYPES if kind == "image" else VIDEO_MIME_TYPES
    )
    if mime_type == "video/quicktime":
        # Google's examples use video/mov for QuickTime payloads.
        mime_type = "video/mov"
    try:
        return {
            "type": kind,
            "data": base64.b64encode(input_path.read_bytes()).decode("ascii"),
            "mime_type": mime_type,
        }
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _probe_video_duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def _read_previous_result(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    resolved = _resolve_file(path, kind="previous result metadata")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Invalid previous result JSON: {resolved}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"Previous result must contain a JSON object: {resolved}")
    return payload


def _resolve_previous_interaction_id(
    explicit: str | None, previous_result: dict[str, Any] | None
) -> str | None:
    from_result = None
    if previous_result is not None:
        value = previous_result.get("interaction_id")
        if isinstance(value, str) and value:
            from_result = value
    if explicit and from_result and explicit != from_result:
        raise ConfigError(
            "--previous-interaction-id disagrees with --previous-result interaction_id."
        )
    return explicit or from_result


def _compute_state_total_duration(
    *,
    operation: str | None,
    requested_duration: int | None,
    source_video_duration: float | None,
    previous_result: dict[str, Any] | None,
) -> float | None:
    previous_total: float | None = None
    if previous_result is not None:
        value = previous_result.get("state_total_duration_seconds")
        if isinstance(value, (int, float)):
            previous_total = float(value)

    if operation == "extend":
        base = previous_total if previous_total is not None else source_video_duration
        if base is not None and requested_duration is not None:
            return base + requested_duration
        return None

    if previous_total is not None:
        # An edit preserves the previous chain's duration.
        if operation == "edit":
            return previous_total
        return None

    if source_video_duration is not None and operation == "edit":
        return source_video_duration
    if requested_duration is not None and operation not in {"edit", "extend"}:
        return float(requested_duration)
    return None


def _validate_limits(
    *,
    model: str,
    operation: str | None,
    duration: int | None,
    source_video: Path | None,
    video_refs: Sequence[Reference],
    previous_interaction_id: str | None,
    previous_result: dict[str, Any] | None,
) -> tuple[list[str], float | None]:
    warnings: list[str] = []
    if duration is not None and not 3 <= duration <= 10:
        raise ConfigError("--duration must be between 3 and 10 seconds.")
    if len(video_refs) > 3:
        raise ConfigError("Gemini Omni supports at most 3 video references.")

    for ref in video_refs:
        ref_duration = _probe_video_duration(ref.path)
        if ref_duration is None:
            warnings.append(
                f"Could not verify @{ref.alias} duration; video refs must be <=3 seconds."
            )
        elif ref_duration > 3.05:
            raise ConfigError(
                f"Video reference @{ref.alias} is {ref_duration:.2f}s; Omni's limit is 3s."
            )

    source_duration = None
    if source_video is not None:
        source_duration = _probe_video_duration(source_video)
        source_max_seconds = (
            30
            if operation == "extend"
            and model in {"gemini-omni-1.1-flash-preview", "gemini-omni-flash-preview"}
            else 10
        )
        if source_duration is None:
            warnings.append(
                f"Could not verify uploaded source duration; this operation expects <= {source_max_seconds}s."
            )
        elif source_duration > source_max_seconds + 0.05:
            raise ConfigError(
                f"Uploaded source video is {source_duration:.2f}s; this Omni surface's current limit is {source_max_seconds}s."
            )

    if operation in {"edit", "extend"} and not source_video and not previous_interaction_id:
        raise ConfigError(
            f"{operation} requires --video/--extend or a previous interaction."
        )

    state_total = _compute_state_total_duration(
        operation=operation,
        requested_duration=duration,
        source_video_duration=source_duration,
        previous_result=previous_result,
    )
    if operation == "extend" and state_total is not None and state_total > 40.05:
        raise ConfigError(
            f"This extension would reach {state_total:.2f}s; Omni multi-turn extension "
            "is documented up to 40s total."
        )
    if operation == "extend" and previous_interaction_id and previous_result is None:
        warnings.append(
            "40s chain length cannot be verified from a raw --previous-interaction-id. "
            "Use --previous-result to enable local chain-duration validation."
        )
    return warnings, state_total


def _build_input(
    compiled: CompiledRequest, *, strip_audio: bool = False
) -> str | list[dict[str, str]]:
    if not compiled.images_in_order and not compiled.videos_in_order:
        return compiled.prompt
    request_input: list[dict[str, str]] = []
    request_input.extend(
        _media_input(path, kind="image") for path in compiled.images_in_order
    )
    request_input.extend(
        _media_input(path, kind="video", strip_audio=strip_audio)
        for path in compiled.videos_in_order
    )
    request_input.append({"type": "text", "text": compiled.prompt})
    return request_input


def _response_format(
    *,
    aspect_ratio: str | None,
    duration: int | None,
    resolution: str | None,
    delivery: str,
    backend: str,
) -> dict[str, str]:
    fmt: dict[str, str] = {"type": "video"}
    if aspect_ratio:
        fmt["aspect_ratio"] = aspect_ratio
    if duration is not None:
        fmt["duration"] = f"{duration}s"
    if resolution:
        fmt["resolution"] = resolution

    resolved_delivery = delivery
    if delivery == "auto":
        # Existing workstation auth is Vertex ADC. Keep it inline: Vertex URI
        # delivery requires caller-owned GCS plumbing, while inline works with
        # the existing project auth and is the least surprising default.
        resolved_delivery = "inline" if backend == "vertex" else (
            "uri" if resolution in {"1080p", "4k"} else "inline"
        )
    if resolved_delivery == "uri":
        if backend == "vertex":
            raise ConfigError(
                "URI delivery on Vertex requires a GCS destination. Use --delivery inline "
                "with existing ADC auth for now."
            )
        fmt["delivery"] = "uri"
    return fmt


def _download_uri_video(client: Any, uri: str, output: Path) -> None:
    """Download Developer-API URI output using the SDK's Files service."""
    output.parent.mkdir(parents=True, exist_ok=True)
    match = re.search(r"files/([^/:?]+)", uri)
    if not match:
        raise ApiError(f"Could not parse generated file ID from URI: {uri}")
    file_name = f"files/{match.group(1)}"
    try:
        while True:
            info = client.files.get(name=file_name)
            state = getattr(getattr(info, "state", None), "name", None)
            if state is None:
                state = str(getattr(info, "state", ""))
            if state == "ACTIVE":
                break
            if state == "FAILED":
                raise ApiError(f"Generated video file failed processing: {file_name}")
            time.sleep(5)
        client.files.download(file=uri, destination=str(output))
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(f"Could not download generated URI output: {exc}") from exc


def _save_output(client: Any, output_video: Any, output: Path) -> tuple[str | None, str | None]:
    data = getattr(output_video, "data", None)
    uri = getattr(output_video, "uri", None)
    mime_type = getattr(output_video, "mime_type", None)
    output.parent.mkdir(parents=True, exist_ok=True)
    if data:
        payload = base64.b64decode(data) if isinstance(data, str) else bytes(data)
        output.write_bytes(payload)
        return uri, mime_type
    if uri:
        _download_uri_video(client, uri, output)
        return uri, mime_type
    raise ApiError("Gemini completed without returning video data or a video URI.")


def generate(
    *,
    client_info: ClientInfo,
    compiled: CompiledRequest,
    output: Path,
    previous_interaction_id: str | None,
    model: str,
    operation: str | None,
    task: str | None,
    store: bool,
    aspect_ratio: str | None,
    duration: int | None,
    resolution: str | None,
    delivery: str,
    strip_audio: bool,
    timeout: int,
    warnings: Sequence[str],
    state_total_duration: float | None,
) -> Result:
    response_format = _response_format(
        aspect_ratio=aspect_ratio,
        duration=duration,
        resolution=resolution,
        delivery=delivery,
        backend=client_info.backend,
    )
    generation_config = (
        {"video_config": {"task": task}} if task is not None else None
    )

    kwargs: dict[str, Any] = {
        "model": model,
        "input": _build_input(compiled, strip_audio=strip_audio),
        "response_format": response_format,
        "store": store,
        "timeout": timeout,
    }
    if generation_config is not None:
        kwargs["generation_config"] = generation_config
    if previous_interaction_id is not None:
        kwargs["previous_interaction_id"] = previous_interaction_id

    try:
        interaction = client_info.client.interactions.create(**kwargs)
    except Exception as exc:
        raise ApiError(f"Gemini Omni request failed: {exc}") from exc

    output_video = getattr(interaction, "output_video", None)
    if output_video is None:
        raise ApiError("Gemini interaction completed without output_video.")
    output_uri, mime_type = _save_output(client_info.client, output_video, output)

    return Result(
        interaction_id=getattr(interaction, "id", None),
        previous_interaction_id=previous_interaction_id,
        model=getattr(interaction, "model", model),
        backend=client_info.backend,
        operation=operation,
        task=task,
        store=store,
        output_path=str(output),
        output_uri=output_uri,
        output_mime_type=mime_type,
        requested_duration_seconds=duration,
        state_total_duration_seconds=state_total_duration,
        compiled_prompt=compiled.prompt,
        warnings=tuple(warnings),
    )


def capabilities() -> dict[str, Any]:
    """Machine-readable contract for an agent deciding how to call this script."""
    return {
        "script": ".agents/skills/gemini-omni-flash-api/scripts/video/generate_video.py",
        "default_model": DEFAULT_MODEL,
        "known_cloud_model": "gemini-omni-1.1-flash-preview",
        "purpose": "Low-level, project-agnostic Gemini Omni video API adapter.",
        "prompt_references": {
            "native": {
                "first_frame": "<FIRST_FRAME>",
                "last_frame": "<LAST_FRAME>",
                "image_reference": "<IMAGE_REF_N>, zero-indexed",
                "video_reference": "<VIDEO_REF_N>, zero-indexed",
            },
            "friendly_handles": {
                "image": "--image-ref dog.png allows @dog; --image-ref hero=dog.png allows @hero",
                "video": "--video-ref motion.mp4 allows @motion",
                "rule": "@handles compile to native <IMAGE_REF_N>/<VIDEO_REF_N> before Google sees the prompt.",
            },
            "binding": "The script constructs [# Sources ...] and [# References ...] from actual media order.",
        },
        "tasks": {
            "values": list(TASKS),
            "default": None,
            "note": "Task is a real Google video_config field but is optional; omit it when inference is sufficient.",
        },
        "operation": {
            "values": ["edit", "extend"],
            "sent_to_google": False,
            "note": "Local-only intent for state tracking/validation. Use --operation extend with previous_interaction_id; Cloud Omni rejects combining previous_interaction_id with video_config.task.",
        },
        "output": {
            "videos_per_interaction": 1,
            "count_parameter": None,
            "aspect_ratios": list(ASPECT_RATIOS),
            "duration_seconds": {"min": 3, "max": 10},
            "resolutions": list(RESOLUTIONS),
            "resolution_default_at_google": "720p",
            "fps": 24,
        },
        "editing": {
            "uploaded_video": "Use --video PATH; current uploaded input limit is <=10s.",
            "stateful": "Use --previous-interaction-id or --previous-result; every successful call returns a new interaction_id.",
            "voice_editing_supported": False,
            "note": "--video marks a local edit operation without forcing Google's optional task field.",
        },
        "interaction_state": {
            "store_default": True,
            "note": "Interactions are stored by default so returned interaction_id values can be used for later stateful edits/extensions. Use --no-store only when multi-turn state is not needed.",
        },
        "extension": {
            "uploaded_video_supported": True,
            "developer_api_generated_video_multiturn_supported": True,
            "developer_api_uploaded_input_max_seconds": 10,
            "cloud_preview_uploaded_input_max_seconds": 30,
            "cloud_preview_previous_interaction_extension": False,
            "extension_seconds": {"min": 3, "max": 10},
            "generated_video_max_total_seconds": 40,
            "position": "end only; no prepend/middle extension",
            "tracking": "Developer API can use --previous-result/--operation extend; Cloud preview uses --extend VIDEO --task extend.",
            "note": "Extension semantics differ by surface; --capabilities documents both rather than pretending they are interchangeable.",
        },
        "video_references": {
            "max_count": 3,
            "max_seconds_each": 3,
            "audio_is_ignored": True,
        },
        "image_references": {
            "hard_max_documented": None,
            "note": "The current Google guide demonstrates 6 image references in one prompt; this script does not invent a lower hard cap.",
        },
        "delivery": {
            "values": list(DELIVERY_MODES),
            "default": "auto",
            "note": "Existing Vertex ADC defaults to inline. Developer API may use URI for 1080p/4k.",
        },
        "audio_input": {
            "strip_audio_flag": "--strip-audio",
            "note": "Removes audio from uploaded video inputs with ffmpeg before sending them to Omni.",
        },
        "agent_workflow": [
            "1. Build the complete final prompt before invoking the script.",
            "2. Use native Omni tokens or @file/alias handles for references.",
            "3. Run --dry-run when bindings are non-trivial or before a costly generation.",
            "4. Prefer --json/--metadata-out and keep interaction_id for later edit/extension.",
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Standalone Gemini Omni 1.1 Flash video client.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Reference syntax:\n"
            "  --image-ref dog.png          => @dog or <IMAGE_REF_0>\n"
            "  --image-ref hero=dog.png     => @hero or <IMAGE_REF_0>\n"
            "  --video-ref motion.mp4       => @motion or <VIDEO_REF_0>\n"
            "  --first-frame start.png      => <FIRST_FRAME>\n"
            "  --last-frame end.png         => <LAST_FRAME>\n\n"
            "The @ syntax is local convenience only; Google receives native Omni tokens."
        ),
    )
    parser.add_argument(
        "prompt_positional",
        nargs="?",
        help="Prompt text as a positional argument (upstream-compatible shorthand).",
    )
    parser.add_argument("--prompt", help="Final Omni prompt text.")
    parser.add_argument("--prompt-file", type=Path, help="UTF-8 file containing the final prompt.")
    parser.add_argument("--output", "-o", type=Path, help="Destination MP4 path.")
    parser.add_argument(
        "--metadata-out",
        type=Path,
        help="Optional JSON result metadata, including interaction_id for later turns.",
    )
    parser.add_argument(
        "--previous-result",
        type=Path,
        help="JSON metadata from a previous run; supplies interaction_id and known chain duration.",
    )
    parser.add_argument(
        "--previous-interaction-id",
        help="Raw previous interaction ID for stateful edit/extension.",
    )
    parser.add_argument("--first-frame", type=Path, help="Literal starting frame image.")
    parser.add_argument(
        "--last-frame",
        type=Path,
        help="Literal final frame image; requires --first-frame.",
    )
    parser.add_argument(
        "--image-ref",
        "--image",
        "--image-reference",
        "--ref-image",
        dest="image_ref",
        action="append",
        default=[],
        metavar="[ALIAS=]PATH",
        help="Reference image; repeat. Alias defaults to filename stem.",
    )
    parser.add_argument(
        "--video-ref",
        "--video-reference",
        "--ref-video",
        dest="video_ref",
        action="append",
        default=[],
        metavar="[ALIAS=]PATH",
        help="Reference video; repeat, max 3 and <=3s each.",
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--video", type=Path, help="Uploaded source video for editing."
    )
    source_group.add_argument(
        "--extend", type=Path, help="Uploaded source video for extension."
    )
    parser.add_argument(
        "--task",
        choices=TASKS,
        help="Optional explicit Google task. Usually omit and let Omni infer it.",
    )
    parser.add_argument(
        "--operation",
        choices=("edit", "extend"),
        help=(
            "Local-only stateful intent; not sent to Google. Use this with "
            "--previous-interaction-id/--previous-result instead of --task."
        ),
    )
    parser.add_argument("--aspect-ratio", choices=ASPECT_RATIOS)
    parser.add_argument("--duration", type=int, metavar="SECONDS")
    parser.add_argument("--resolution", choices=RESOLUTIONS)
    parser.add_argument(
        "--delivery",
        choices=DELIVERY_MODES,
        default="auto",
        help="Output transport. auto respects the active Google backend.",
    )
    parser.add_argument(
        "--strip-audio",
        "-a",
        action="store_true",
        help="Strip audio from uploaded video inputs before sending them to Omni.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument(
        "--store",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Persist the interaction for later previous_interaction_id use (default: true).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the compiled request without calling Google.",
    )
    parser.add_argument(
        "--capabilities",
        action="store_true",
        help="Print machine-readable capabilities/limits JSON and exit.",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print successful result as JSON."
    )
    return parser


def _prepare(args: argparse.Namespace) -> tuple[
    str,
    Path | None,
    Path | None,
    list[Reference],
    list[Reference],
    Path | None,
    dict[str, Any] | None,
    str | None,
]:
    prompt = _read_prompt(args.prompt, args.prompt_file)

    first_frame = (
        _resolve_file(args.first_frame, kind="first frame") if args.first_frame else None
    )
    last_frame = (
        _resolve_file(args.last_frame, kind="last frame") if args.last_frame else None
    )
    if last_frame is not None and first_frame is None:
        raise ConfigError("--last-frame requires --first-frame.")
    if first_frame is not None:
        _mime_type(first_frame, IMAGE_MIME_TYPES)
    if last_frame is not None:
        _mime_type(last_frame, IMAGE_MIME_TYPES)

    image_refs = _parse_references(args.image_ref, kind="image")
    video_refs = _parse_references(args.video_ref, kind="video")
    _validate_cross_kind_aliases(image_refs, video_refs)

    source_arg = args.video or args.extend
    source_video = (
        _resolve_file(source_arg, kind="source video") if source_arg is not None else None
    )
    if source_video is not None:
        _mime_type(source_video, VIDEO_MIME_TYPES)

    previous_result = _read_previous_result(args.previous_result)
    previous_interaction_id = _resolve_previous_interaction_id(
        args.previous_interaction_id, previous_result
    )
    return (
        prompt,
        first_frame,
        last_frame,
        image_refs,
        video_refs,
        source_video,
        previous_result,
        previous_interaction_id,
    )


def _dry_run_payload(
    *,
    compiled: CompiledRequest,
    args: argparse.Namespace,
    operation: str | None,
    previous_interaction_id: str | None,
    warnings: Sequence[str],
    state_total_duration: float | None,
) -> dict[str, Any]:
    return {
        "compiled_prompt": compiled.prompt,
        "images_in_order": [str(path) for path in compiled.images_in_order],
        "videos_in_order": [str(path) for path in compiled.videos_in_order],
        "image_refs": [
            {"alias": ref.alias, "path": str(ref.path), "token": f"<IMAGE_REF_{idx}>"}
            for idx, ref in enumerate(compiled.image_refs)
        ],
        "video_refs": [
            {"alias": ref.alias, "path": str(ref.path), "token": f"<VIDEO_REF_{idx}>"}
            for idx, ref in enumerate(compiled.video_refs)
        ],
        "request": {
            "model": args.model,
            "operation": operation,
            "task": args.task,
            "store": args.store,
            "aspect_ratio": args.aspect_ratio,
            "duration_seconds": args.duration,
            "resolution": args.resolution,
            "delivery": args.delivery,
            "strip_audio": args.strip_audio,
            "previous_interaction_id": previous_interaction_id,
        },
        "known_state_total_duration_seconds": state_total_duration,
        "warnings": list(warnings),
    }


def _result_payload(result: Result) -> dict[str, Any]:
    payload = asdict(result)
    payload["warnings"] = list(result.warnings)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.capabilities:
            print(json.dumps(capabilities(), indent=2))
            return 0
        if args.prompt is None and args.prompt_positional is not None:
            args.prompt = args.prompt_positional
        if not args.dry_run and args.output is None:
            raise ConfigError("--output is required unless using --dry-run/--capabilities.")

        (
            prompt,
            first_frame,
            last_frame,
            image_refs,
            video_refs,
            source_video,
            previous_result,
            previous_interaction_id,
        ) = _prepare(args)

        if previous_interaction_id is not None and args.task is not None:
            raise ConfigError(
                "Google does not allow video_config.task with previous_interaction_id "
                "on the stateful Omni path. Use --operation edit|extend instead."
            )
        if args.extend is not None and args.task not in {None, "extend"}:
            raise ConfigError("--extend conflicts with a non-extend --task.")
        if args.video is not None and args.task == "extend":
            raise ConfigError("Use --extend PATH instead of --video PATH with --task extend.")
        if args.extend is not None and args.operation not in {None, "extend"}:
            raise ConfigError("--extend conflicts with --operation edit.")
        if args.video is not None and args.operation not in {None, "edit"}:
            raise ConfigError("--video conflicts with --operation extend.")

        operation = (
            args.operation
            if args.operation is not None
            else "extend"
            if args.extend is not None
            else "edit"
            if args.video is not None
            else args.task
            if args.task in {"edit", "extend"}
            else None
        )

        if (
            operation == "extend"
            and previous_interaction_id is not None
            and args.model in {"gemini-omni-1.1-flash-preview", "gemini-omni-flash-preview"}
        ):
            raise ConfigError(
                "Gemini Enterprise Agent Platform extension does not use "
                "previous_interaction_id. Extend the generated MP4 with "
                "--extend PATH --task extend instead."
            )
        if (
            operation == "extend"
            and source_video is not None
            and args.model in {"gemini-omni-1.1-flash-preview", "gemini-omni-flash-preview"}
            and args.aspect_ratio is not None
        ):
            raise ConfigError(
                "Gemini Enterprise Agent Platform inherits aspect ratio from the "
                "source video for extend; omit --aspect-ratio."
            )

        warnings, state_total_duration = _validate_limits(
            model=args.model,
            operation=operation,
            duration=args.duration,
            source_video=source_video,
            video_refs=video_refs,
            previous_interaction_id=previous_interaction_id,
            previous_result=previous_result,
        )
        compiled = compile_request(
            prompt=prompt,
            first_frame=first_frame,
            last_frame=last_frame,
            image_refs=image_refs,
            source_video=source_video,
            video_refs=video_refs,
        )
        warnings.extend(
            f"Supplied reference @{alias} is not used in the prompt."
            for alias in compiled.unused_aliases
        )

        if args.dry_run:
            print(
                json.dumps(
                    _dry_run_payload(
                        compiled=compiled,
                        args=args,
                        operation=operation,
                        previous_interaction_id=previous_interaction_id,
                        warnings=warnings,
                        state_total_duration=state_total_duration,
                    ),
                    indent=2,
                )
            )
            return 0

        client_info = create_client(args.model)
        output = args.output.expanduser().resolve()
        result = generate(
            client_info=client_info,
            compiled=compiled,
            output=output,
            previous_interaction_id=previous_interaction_id,
            model=args.model,
            operation=operation,
            task=args.task,
            store=args.store,
            aspect_ratio=args.aspect_ratio,
            duration=args.duration,
            resolution=args.resolution,
            delivery=args.delivery,
            strip_audio=args.strip_audio,
            timeout=args.timeout,
            warnings=warnings,
            state_total_duration=state_total_duration,
        )
        payload = _result_payload(result)

        if args.metadata_out is not None:
            metadata_out = args.metadata_out.expanduser().resolve()
            metadata_out.parent.mkdir(parents=True, exist_ok=True)
            metadata_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Using {client_info.label}")
            print(f"Saved video: {result.output_path}")
            if result.interaction_id:
                print(f"interaction_id: {result.interaction_id}")
            if args.metadata_out is not None:
                print(f"metadata: {args.metadata_out.expanduser().resolve()}")
            for warning in result.warnings:
                print(f"warning: {warning}", file=sys.stderr)
        return 0
    except OmniVideoError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
