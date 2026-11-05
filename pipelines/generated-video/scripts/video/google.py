"""Google Gemini Omni Flash video generation provider using the Interactions API."""

from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any, Sequence

# Prevent local script directory from shadowing top-level google namespace package
if sys.path and Path(sys.path[0]).resolve() == Path(__file__).parent.resolve():
    sys.path.pop(0)

try:
    from .base import BaseProvider, ProviderUnavailableError, VideoError
except ImportError:
    from base import BaseProvider, ProviderUnavailableError, VideoError  # type: ignore


DEFAULT_MODEL = "gemini-omni-flash-preview"
TASKS = ("text_to_video", "image_to_video", "reference_to_video", "edit")


def image_input(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"Reference image does not exist: {path}")

    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError(f"Unsupported reference image type: {path}")

    return {
        "type": "image",
        "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        "mime_type": mime_type,
    }


def video_input(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"Input video does not exist: {path}")

    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type not in {"video/mp4", "video/mpeg", "video/quicktime", "video/webm"}:
        raise ValueError(f"Unsupported input video type: {path}")

    return {
        "type": "video",
        "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        "mime_type": "video/mov" if mime_type == "video/quicktime" else mime_type,
    }


def video_response_format(task: str | None, aspect_ratio: str) -> dict[str, str]:
    if task == "edit":
        return {"type": "video"}
    return {"type": "video", "aspect_ratio": aspect_ratio}


def create_client(backend: str = "auto", gcp_project: str | None = None) -> tuple[Any, str]:
    """Create one authenticated Gemini client for one or many generations."""
    try:
        from google import genai
    except ImportError as exc:
        raise ProviderUnavailableError(
            "Install project dependencies first: python3 -m pip install -e ."
        ) from exc

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    cloud_project = (
        gcp_project
        or os.getenv("GCP_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    if not cloud_project and backend in {"auto", "vertex"}:
        try:
            import google.auth

            _, cloud_project = google.auth.default()
        except Exception:
            pass

    use_vertex = backend == "vertex" or (backend == "auto" and bool(cloud_project))
    if use_vertex:
        if not cloud_project:
            raise ProviderUnavailableError("Vertex backend requires Google Cloud ADC and a project ID.")
        client = genai.Client(vertexai=True, project=cloud_project, location="global")
        return client, f"Gemini Enterprise Agent Platform project {cloud_project}"

    if not api_key:
        raise ProviderUnavailableError("Developer backend requires GEMINI_API_KEY or GOOGLE_API_KEY.")
    return genai.Client(api_key=api_key), "Gemini Developer API"


class GoogleProvider(BaseProvider):
    """Generates videos using Google Gemini Omni Flash Interactions API."""

    name = "google"

    def __init__(
        self,
        backend: str = "auto",
        gcp_project: str | None = None,
        client: Any = None,
    ) -> None:
        self.backend = backend
        self.gcp_project = gcp_project
        self._client: Any = client
        self._backend_label: str = ""

    def _ensure_client(self) -> Any:
        if self._client is None:
            self._client, self._backend_label = create_client(self.backend, self.gcp_project)
        return self._client

    def preflight(self) -> bool:
        try:
            self._ensure_client()
            return True
        except Exception as exc:
            print(f"Google preflight check failed: {exc}")
            return False

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
        client: Any = None,
        **kwargs: Any,
    ) -> int:
        active_client = client or self._ensure_client()
        target_model = model or DEFAULT_MODEL

        request_input: str | list[dict[str, str]]
        if videos or images:
            request_input = [video_input(path) for path in videos]
            request_input.extend(image_input(path) for path in images)
            request_input.append({"type": "text", "text": prompt})
        else:
            request_input = prompt

        generation_config = None
        if task:
            generation_config = {"video_config": {"task": task}}

        try:
            interaction = active_client.interactions.create(
                model=target_model,
                input=request_input,
                response_format=video_response_format(task, aspect_ratio),
                generation_config=generation_config,
                timeout=600,
            )
        except Exception as exc:
            raise VideoError(f"Gemini generation request failed: {exc}") from exc

        output_video = getattr(interaction, "output_video", None)
        encoded_video = getattr(output_video, "data", None)
        if not encoded_video:
            raise VideoError("Gemini completed without returning inline video data.")

        video_bytes = (
            base64.b64decode(encoded_video)
            if isinstance(encoded_video, str)
            else bytes(encoded_video)
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(video_bytes)
        return len(video_bytes)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate video with Google Gemini Omni Flash.")
    parser.add_argument("--prompt", "-p", required=True, help="Omni Flash video prompt")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Destination .mp4 path")
    parser.add_argument(
        "--image",
        type=Path,
        action="append",
        default=[],
        help="Reference image; repeat in order of <IMAGE_REF_N>",
    )
    parser.add_argument(
        "--video",
        type=Path,
        action="append",
        default=[],
        help="Input video for editing",
    )
    parser.add_argument("--task", choices=TASKS, default=None)
    parser.add_argument("--aspect-ratio", choices=("16:9", "9:16"), default="16:9")
    parser.add_argument(
        "--backend",
        choices=("auto", "vertex", "developer"),
        default="auto",
        help="Authentication backend",
    )
    parser.add_argument("--gcp-project", default=None, help="Google Cloud project override")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model ID")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    provider = GoogleProvider(backend=args.backend, gcp_project=args.gcp_project)
    print(f"Connecting to Google backend ({args.backend})...")
    provider._ensure_client()
    print(f"Using {provider._backend_label}")
    byte_count = provider.generate_video(
        prompt=args.prompt,
        output=args.output,
        images=args.image,
        videos=args.video,
        task=args.task,
        aspect_ratio=args.aspect_ratio,
        model=args.model,
    )
    print(f"Saved {byte_count:,} bytes to {args.output}")


if __name__ == "__main__":
    main()
