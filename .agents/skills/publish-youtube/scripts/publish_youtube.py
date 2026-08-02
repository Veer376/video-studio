#!/usr/bin/env python3
"""Publish Story Video Maker projects to YouTube."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

YOUTUBE_SCRIPTS = Path(__file__).resolve().parents[2] / "youtube" / "scripts"
if not YOUTUBE_SCRIPTS.exists():
    YOUTUBE_SCRIPTS = Path.cwd() / ".agents" / "skills" / "youtube" / "scripts"
sys.path.insert(0, str(YOUTUBE_SCRIPTS))

from youtube_lib.auth import youtube_client  # noqa: E402
from youtube_lib.common import (  # noqa: E402
    SUPPORTED_THUMBNAIL_SUFFIXES,
    THUMBNAIL_MAX_BYTES,
    die,
    parse_video_id,
    read_json,
    sha256_json,
    utc_now,
    video_url,
)
from youtube_lib.data import fetch_video_resource  # noqa: E402
from youtube_lib.media import compress_thumbnail, ensure_uploadable_thumbnail  # noqa: E402
from youtube_lib.upload import print_upload_result, upload_file  # noqa: E402


def write_upload_json(project_dir: Path, payload: dict[str, Any]) -> Path:
    out = project_dir / "youtube" / "upload.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def project_paths(project_dir: Path) -> dict[str, Path]:
    return {
        "video": project_dir / "output" / "final-video.mp4",
        "metadata": project_dir / "youtube" / "metadata.json",
        "upload": project_dir / "youtube" / "upload.json",
        "thumbnails": project_dir / "youtube" / "thumbnails",
    }


def normalize_project_dir(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.exists():
        die(f"project folder does not exist: {p}")
    if not p.is_dir():
        die(f"project path is not a folder: {p}")
    return p


def resolve_project_thumbnail(project_dir: Path, value: str | None) -> tuple[Path | None, str | None]:
    thumbnails_dir = project_paths(project_dir)["thumbnails"]
    if value:
        raw = Path(value).expanduser()
        candidates = [raw] if raw.is_absolute() else [thumbnails_dir / raw, project_dir / raw, raw]
    else:
        candidates = [
            thumbnails_dir / "thumbnail-01.png",
            thumbnails_dir / "thumbnail-01.jpg",
            thumbnails_dir / "thumbnail-01.jpeg",
        ]

    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if not path.exists() or not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_THUMBNAIL_SUFFIXES:
            return None, f"unsupported thumbnail extension: {path}"
        return path, None

    if value:
        return None, f"selected thumbnail not found: {value}"
    return None, "default thumbnail-01 image not found"


def tags_from_metadata(metadata: dict[str, Any]) -> list[str]:
    tags = metadata.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(tags, list):
        return []
    return [str(t) for t in tags]


def upload_state_from_video(project_dir: Path, video_id: str, item: dict[str, Any] | None) -> dict[str, Any]:
    status = item.get("status", {}) if item else {}
    processing = item.get("processingDetails", {}) if item else {}
    snippet = item.get("snippet", {}) if item else {}
    return {
        "state": "fetched" if item else "not_found",
        "video_id": video_id,
        "url": video_url(video_id),
        "visibility": status.get("privacyStatus"),
        "upload_status": status.get("uploadStatus"),
        "processing_status": processing.get("processingStatus", "not_found" if not item else "unknown"),
        "project": str(project_dir),
        "video_path": None,
        "video_sha256": None,
        "metadata_path": None,
        "metadata_sha256": None,
        "thumbnail_path": None,
        "thumbnail_sha256": None,
        "thumbnail_warning": None,
        "thumbnail_error": None,
        "uploaded_at": snippet.get("publishedAt"),
        "last_checked_at": utc_now(),
        "status_response": {"items": [item] if item else []},
    }


def command_publish(args: argparse.Namespace) -> None:
    project_dir = normalize_project_dir(args.project_dir)
    paths = project_paths(project_dir)

    if paths["upload"].exists() and not args.force:
        print(f"upload_json_exists {paths['upload']}")
        print("not re-uploading; checking status instead")
        command_status(args)
        return

    if not paths["video"].exists():
        die(f"missing final video: {paths['video']}")

    metadata = read_json(paths["metadata"])
    title = metadata.get("recommended_title") or metadata.get("title")
    description = metadata.get("description")
    if not title:
        die("metadata.json must include recommended_title or title")
    if not description:
        die("metadata.json must include description")

    thumbnail, thumbnail_warning = resolve_project_thumbnail(project_dir, args.thumbnail)
    if thumbnail is None and args.thumbnail:
        die(thumbnail_warning or "thumbnail not found")
    if thumbnail is not None:
        thumbnail, compressed_warning, compression = ensure_uploadable_thumbnail(
            thumbnail,
            quality=args.thumbnail_quality,
            scale_percent=args.thumbnail_scale_percent,
        )
        thumbnail_warning = compressed_warning or thumbnail_warning
    else:
        compression = None

    payload = upload_file(
        youtube_client("upload"),
        video_path=paths["video"],
        title=str(title),
        description=str(description),
        visibility=args.visibility,
        thumbnail=thumbnail,
        tags=tags_from_metadata(metadata),
        category_id=str(metadata.get("categoryId") or metadata.get("category_id") or "22"),
        made_for_kids=bool(metadata.get("selfDeclaredMadeForKids", False)),
        thumbnail_quality=args.thumbnail_quality,
        thumbnail_scale_percent=args.thumbnail_scale_percent,
    )
    payload.update(
        {
            "project": str(project_dir),
            "metadata_path": str(paths["metadata"]),
            "metadata_sha256": sha256_json(metadata),
            "thumbnail_warning": thumbnail_warning,
            "thumbnail_compression": payload.get("thumbnail_compression") or compression,
        }
    )
    out = write_upload_json(project_dir, payload)
    print_upload_result(payload)
    print(f"saved {out}")


def command_status(args: argparse.Namespace) -> None:
    project_dir = normalize_project_dir(args.project_dir)
    paths = project_paths(project_dir)
    if not paths["upload"].exists():
        die(f"missing upload state: {paths['upload']}")

    payload = read_json(paths["upload"])
    video_id = payload.get("video_id")
    if not video_id:
        die(f"upload.json does not contain video_id: {paths['upload']}")

    item = fetch_video_resource(youtube_client("manage"), video_id, include_processing=True)
    status = item.get("status", {}) if item else {}
    processing = item.get("processingDetails", {}) if item else {}
    payload.update(
        {
            "state": "status_checked" if item else "not_found",
            "last_checked_at": utc_now(),
            "visibility": status.get("privacyStatus", payload.get("visibility")),
            "upload_status": status.get("uploadStatus"),
            "processing_status": processing.get("processingStatus", "unknown" if item else "not_found"),
            "status_response": {"items": [item] if item else []},
        }
    )
    out = write_upload_json(project_dir, payload)
    print(f"video_id {video_id}")
    print(f"url {payload.get('url')}")
    print(f"state {payload['state']}")
    print(f"visibility {payload.get('visibility')}")
    print(f"upload_status {payload.get('upload_status')}")
    print(f"processing_status {payload.get('processing_status')}")
    print(f"saved {out}")


def command_attach(args: argparse.Namespace) -> None:
    project_dir = normalize_project_dir(args.project_dir)
    video_id = parse_video_id(args.video)
    paths = project_paths(project_dir)
    existing = read_json(paths["upload"]) if paths["upload"].exists() else None
    if existing and existing.get("video_id") and existing.get("video_id") != video_id and not args.force:
        die(
            f"{paths['upload']} already points to {existing.get('video_id')}; "
            "use --force to attach a different video"
        )

    item = fetch_video_resource(youtube_client("manage"), video_id)
    payload = existing or {}
    payload.update(upload_state_from_video(project_dir, video_id, item))
    out = write_upload_json(project_dir, payload)
    print(f"video_id {video_id}")
    print(f"url {video_url(video_id)}")
    print(f"state {payload['state']}")
    print(f"saved {out}")


def command_compress_thumbnail(args: argparse.Namespace) -> None:
    project_dir = normalize_project_dir(args.project_dir)
    source, warning = resolve_project_thumbnail(project_dir, args.thumbnail)
    if source is None:
        die(warning or "thumbnail not found")

    output = Path(args.output).expanduser() if args.output else None
    if output and not output.is_absolute():
        output = project_paths(project_dir)["thumbnails"] / output

    out, info = compress_thumbnail(
        source,
        quality=args.quality,
        scale_percent=args.scale_percent,
        max_bytes=args.max_bytes,
        output=output,
    )
    print(f"source {source}")
    print(f"output {out}")
    print(f"size_bytes {out.stat().st_size}")
    print(f"max_bytes {args.max_bytes}")
    print(f"quality {info.get('quality')}")
    print(f"scale_percent {info.get('scale_percent')}")
    print("status ok" if out.stat().st_size <= args.max_bytes else "status over_limit")


def add_publish_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_dir", help="Path like library/<project_slug>")
    parser.add_argument("--visibility", choices=["private", "unlisted", "public"], default="private")
    parser.add_argument("--thumbnail", help="Thumbnail filename under youtube/thumbnails/ or explicit path.")
    parser.add_argument("--thumbnail-quality", type=int, default=88)
    parser.add_argument("--thumbnail-scale-percent", type=int, default=100)
    parser.add_argument("--force", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Story Video Maker projects to YouTube.")
    sub = parser.add_subparsers(dest="command", required=True)

    publish = sub.add_parser("publish", help="Publish a Story Video Maker project.")
    add_publish_args(publish)
    publish.set_defaults(func=command_publish)

    status = sub.add_parser("status", help="Check an existing project upload.")
    status.add_argument("project_dir", help="Path like library/<project_slug>")
    status.set_defaults(func=command_status)

    attach = sub.add_parser("attach", help="Attach a manually uploaded YouTube video to a project.")
    attach.add_argument("project_dir", help="Path like library/<project_slug>")
    attach.add_argument("video", help="YouTube video id or URL")
    attach.add_argument("--force", action="store_true")
    attach.set_defaults(func=command_attach)

    compress = sub.add_parser("compress-thumbnail", help="Compress a project thumbnail.")
    compress.add_argument("project_dir", help="Path like library/<project_slug>")
    compress.add_argument("--thumbnail", required=True)
    compress.add_argument("--quality", type=int, default=88)
    compress.add_argument("--scale-percent", type=int, default=100)
    compress.add_argument("--max-bytes", type=int, default=THUMBNAIL_MAX_BYTES)
    compress.add_argument("--output")
    compress.set_defaults(func=command_compress_thumbnail)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
