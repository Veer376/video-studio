"""Generate one Gemini Omni Flash video through the Interactions API."""

from __future__ import annotations

import argparse
import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, Sequence


MODEL = "gemini-omni-flash-preview"
TASKS = ("text_to_video", "image_to_video", "reference_to_video", "edit")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Omni Flash video prompt")
    parser.add_argument("--output", type=Path, required=True, help="Destination .mp4 path")
    parser.add_argument(
        "--image",
        type=Path,
        action="append",
        default=[],
        help="Reference image; repeat in the same order used by prompt role tags",
    )
    parser.add_argument(
        "--video",
        type=Path,
        action="append",
        default=[],
        help="Input video for an edit; repeat only when the model supports multiple videos",
    )
    parser.add_argument("--task", choices=TASKS, default=None)
    parser.add_argument("--aspect-ratio", choices=("16:9", "9:16"), default="16:9")
    parser.add_argument(
        "--backend",
        choices=("auto", "vertex", "developer"),
        default="auto",
        help="Authentication backend; auto prefers configured Google Cloud ADC",
    )
    parser.add_argument("--gcp-project", default=None, help="Google Cloud project override")
    return parser.parse_args()


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


def create_client(backend: str, gcp_project: str | None = None) -> tuple[Any, str]:
    """Create one authenticated Gemini client for one or many generations."""
    try:
        from google import genai
    except ImportError as exc:
        raise SystemExit("Install project dependencies first: python3 -m pip install -e .") from exc

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
        except google.auth.exceptions.DefaultCredentialsError:
            pass

    use_vertex = backend == "vertex" or (backend == "auto" and bool(cloud_project))
    if use_vertex:
        if not cloud_project:
            raise SystemExit("Vertex backend requires Google Cloud ADC and a project ID.")
        client = genai.Client(vertexai=True, project=cloud_project, location="global")
        return client, f"Gemini Enterprise Agent Platform project {cloud_project}"

    if not api_key:
        raise SystemExit("Developer backend requires GEMINI_API_KEY or GOOGLE_API_KEY.")
    return genai.Client(api_key=api_key), "Gemini Developer API"


def generate_video(
    *,
    client: Any,
    prompt: str,
    output: Path,
    images: Sequence[Path] = (),
    videos: Sequence[Path] = (),
    task: str | None = None,
    aspect_ratio: str = "16:9",
    model: str = MODEL,
) -> int:
    """Generate one video, save it, and return its byte length."""
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

    interaction = client.interactions.create(
        model=model,
        input=request_input,
        response_format=video_response_format(task, aspect_ratio),
        generation_config=generation_config,
        timeout=600,
    )

    output_video = getattr(interaction, "output_video", None)
    encoded_video = getattr(output_video, "data", None)
    if not encoded_video:
        raise RuntimeError("Gemini completed without returning inline video data.")

    video_bytes = (
        base64.b64decode(encoded_video)
        if isinstance(encoded_video, str)
        else bytes(encoded_video)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(video_bytes)
    return len(video_bytes)


def main() -> None:
    args = parse_args()
    client, backend_label = create_client(args.backend, args.gcp_project)
    print(f"Using {backend_label}")
    byte_count = generate_video(
        client=client,
        prompt=args.prompt,
        output=args.output,
        images=args.image,
        videos=args.video,
        task=args.task,
        aspect_ratio=args.aspect_ratio,
    )
    print(f"Saved {byte_count:,} bytes to {args.output}")


if __name__ == "__main__":
    main()
