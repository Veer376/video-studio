#!/usr/bin/env python3
"""Upload a Story Video Maker project to YouTube.

This script intentionally lives inside the youtube skill. It does not
depend on project src/ code so the upload capability can remain skill-owned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
MANAGE_SCOPE = "https://www.googleapis.com/auth/youtube"
THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024
SUPPORTED_THUMBNAIL_SUFFIXES = {".png", ".jpg", ".jpeg"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def die(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_google_libs() -> tuple[Any, Any, Any, Any, Any, Any]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
    except ModuleNotFoundError as exc:
        die(
            "missing Google API libraries. Install with: "
            "python3 -m pip install --user google-api-python-client "
            "google-auth-oauthlib google-auth-httplib2"
        )
    return Request, Credentials, InstalledAppFlow, build, HttpError, MediaFileUpload


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"missing required file: {path}")
    except json.JSONDecodeError as exc:
        die(f"invalid JSON in {path}: {exc}")


def video_url(video_id: str) -> str:
    return f"https://youtu.be/{video_id}"


def parse_video_id(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value

    parsed = urlparse(value)
    host = parsed.netloc.lower()
    path_parts = [p for p in parsed.path.split("/") if p]

    if host.endswith("youtu.be") and path_parts:
        return path_parts[0]
    if "youtube.com" in host:
        query_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_id:
            return query_id
        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
            return path_parts[1]

    match = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", value)
    if match:
        return match.group(1)

    die(f"could not parse YouTube video id from: {value}")


def write_upload_json(project_dir: Path, payload: dict[str, Any]) -> Path:
    out = project_dir / "youtube" / "upload.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def project_paths(project_dir: Path) -> dict[str, Path]:
    return {
        "video": project_dir / "output" / "final-video.mp4",
        "youtube_dir": project_dir / "youtube",
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


def resolve_thumbnail_path(project_dir: Path, value: str | None) -> tuple[Path | None, str | None]:
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


def load_pillow():
    try:
        from PIL import Image
    except ModuleNotFoundError:
        die("missing Pillow. Install with: python3 -m pip install --user pillow")
    return Image


def compressed_thumbnail_path(source: Path, quality: int, scale_percent: int) -> Path:
    stem = f"{source.stem}-youtube-q{quality}"
    if scale_percent != 100:
        stem += f"-s{scale_percent}"
    return source.with_name(f"{stem}.jpg")


def compress_thumbnail(
    source: Path,
    *,
    quality: int,
    scale_percent: int,
    max_bytes: int = THUMBNAIL_MAX_BYTES,
    output: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    if source.suffix.lower() not in SUPPORTED_THUMBNAIL_SUFFIXES:
        die(f"unsupported thumbnail extension: {source}")
    if not 1 <= quality <= 100:
        die("--quality must be between 1 and 100")
    if not 10 <= scale_percent <= 100:
        die("--scale-percent must be between 10 and 100")

    Image = load_pillow()
    out = output or compressed_thumbnail_path(source, quality, scale_percent)
    image = Image.open(source).convert("RGB")
    original_size = image.size
    if scale_percent != 100:
        resized = (
            max(1, int(original_size[0] * scale_percent / 100)),
            max(1, int(original_size[1] * scale_percent / 100)),
        )
        image = image.resize(resized, Image.Resampling.LANCZOS)

    attempts: list[dict[str, Any]] = []
    current_quality = quality
    while current_quality >= 40:
        image.save(out, "JPEG", quality=current_quality, optimize=True, progressive=True)
        size = out.stat().st_size
        attempts.append({"quality": current_quality, "size_bytes": size})
        if size <= max_bytes:
            return out, {
                "source": str(source),
                "output": str(out),
                "original_size": original_size,
                "final_size": image.size,
                "quality": current_quality,
                "scale_percent": scale_percent,
                "size_bytes": size,
                "max_bytes": max_bytes,
                "attempts": attempts,
            }
        current_quality -= 5

    return out, {
        "source": str(source),
        "output": str(out),
        "original_size": original_size,
        "final_size": image.size,
        "quality": current_quality + 5,
        "scale_percent": scale_percent,
        "size_bytes": out.stat().st_size if out.exists() else None,
        "max_bytes": max_bytes,
        "attempts": attempts,
        "warning": "compressed thumbnail is still over the max byte limit",
    }


def select_thumbnail(
    project_dir: Path,
    *,
    selected: str | None = None,
    quality: int = 88,
    scale_percent: int = 100,
    max_bytes: int = THUMBNAIL_MAX_BYTES,
) -> tuple[Path | None, str | None, dict[str, Any] | None]:
    path, warning = resolve_thumbnail_path(project_dir, selected)
    if path is None:
        return None, warning, None

    size = path.stat().st_size
    if size <= max_bytes:
        return path, None, None

    compressed, info = compress_thumbnail(
        path,
        quality=quality,
        scale_percent=scale_percent,
        max_bytes=max_bytes,
    )
    if compressed.stat().st_size <= max_bytes:
        return compressed, f"compressed oversized thumbnail: {path}", info
    return None, f"thumbnail remains over YouTube API max size after compression: {compressed}", info


def token_path(scope_profile: str) -> Path:
    config_dir = Path.home() / ".config" / "projects"
    if scope_profile == "upload":
        legacy = config_dir / "youtube_token.json"
        if legacy.exists():
            return legacy
        return config_dir / "youtube_token_upload.json"
    if scope_profile == "manage":
        return config_dir / "youtube_token_manage.json"
    die(f"unknown scope profile: {scope_profile}")


def token_candidates(scope_profile: str) -> list[Path]:
    config_dir = Path.home() / ".config" / "projects"
    if scope_profile == "upload":
        return [config_dir / "youtube_token.json", config_dir / "youtube_token_upload.json"]
    if scope_profile == "manage":
        return [config_dir / "youtube_token_manage.json"]
    die(f"unknown scope profile: {scope_profile}")


def reset_tokens(scope_profiles: list[str]) -> list[Path]:
    removed: list[Path] = []
    for scope_profile in scope_profiles:
        for token in token_candidates(scope_profile):
            if token.exists():
                token.unlink()
                removed.append(token)
    return removed


def get_credentials(scope_profile: str):
    Request, Credentials, InstalledAppFlow, *_ = load_google_libs()
    config_dir = Path.home() / ".config" / "projects"
    client_secret = config_dir / "youtube_client_secret.json"
    if not client_secret.exists():
        die(f"missing OAuth client secret: {client_secret}")

    scopes = [UPLOAD_SCOPE] if scope_profile == "upload" else [MANAGE_SCOPE]
    token = token_path(scope_profile)

    creds = None
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), scopes)
            creds = flow.run_local_server(port=0, open_browser=True, prompt="consent")
        token.parent.mkdir(parents=True, exist_ok=True)
        token.write_text(creds.to_json(), encoding="utf-8")
    return creds


def youtube_client(scope_profile: str):
    *_, build, _, _ = load_google_libs()
    return build("youtube", "v3", credentials=get_credentials(scope_profile))


def authenticated_channel(youtube) -> dict[str, Any]:
    response = (
        youtube.channels()
        .list(part="id,snippet,contentDetails,status", mine=True)
        .execute()
    )
    channels = response.get("items", [])
    if not channels:
        die("no authenticated YouTube channel found")
    return channels[0]


def fetch_video_resource(youtube, video_id: str) -> dict[str, Any] | None:
    response = (
        youtube.videos()
        .list(part="snippet,status,processingDetails,statistics,contentDetails", id=video_id)
        .execute()
    )
    items = response.get("items", [])
    return items[0] if items else None


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


def print_video_row(item: dict[str, Any]) -> None:
    video_id = item.get("id") or item.get("contentDetails", {}).get("videoId")
    snippet = item.get("snippet", {})
    status = item.get("status", {})
    stats = item.get("statistics", {})
    title = snippet.get("title", "").replace("\n", " ")[:80]
    published = snippet.get("publishedAt", "")
    privacy = status.get("privacyStatus", "")
    views = stats.get("viewCount", "")
    print(f"{video_id}\t{privacy}\t{views}\t{published}\t{title}")


def print_channel(channel: dict[str, Any]) -> None:
    snippet = channel.get("snippet", {})
    status = channel.get("status", {})
    print(f"channel_id {channel.get('id')}")
    print(f"title {snippet.get('title')}")
    if snippet.get("customUrl"):
        print(f"custom_url {snippet.get('customUrl')}")
    if status.get("privacyStatus"):
        print(f"privacy {status.get('privacyStatus')}")


def command_auth(args: argparse.Namespace) -> None:
    scope_profiles = ["upload", "manage"] if args.scope == "both" else [args.scope]
    if args.reset:
        removed = reset_tokens(scope_profiles)
        if removed:
            for token in removed:
                print(f"removed {token}")
        else:
            print("removed none")

    for scope_profile in scope_profiles:
        get_credentials(scope_profile)
        print(f"authenticated {scope_profile}")

    youtube = youtube_client("manage" if "manage" in scope_profiles else "upload")
    print_channel(authenticated_channel(youtube))


def command_whoami(args: argparse.Namespace) -> None:
    youtube = youtube_client(args.scope)
    channel = authenticated_channel(youtube)
    if args.json:
        print(json.dumps({"channel": channel}, indent=2, ensure_ascii=False))
        return
    print_channel(channel)


def metadata_body(metadata: dict[str, Any], visibility: str) -> dict[str, Any]:
    title = metadata.get("recommended_title") or metadata.get("title")
    description = metadata.get("description")
    if not title:
        die("metadata.json must include recommended_title or title")
    if not description:
        die("metadata.json must include description")

    tags = metadata.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(tags, list):
        tags = []

    snippet: dict[str, Any] = {
        "title": str(title)[:100],
        "description": str(description)[:5000],
        "categoryId": str(metadata.get("categoryId") or metadata.get("category_id") or "22"),
    }
    if tags:
        snippet["tags"] = [str(t) for t in tags][:30]

    return {
        "snippet": snippet,
        "status": {
            "privacyStatus": visibility,
            "selfDeclaredMadeForKids": bool(metadata.get("selfDeclaredMadeForKids", False)),
        },
    }


def upload_thumbnail(youtube, video_id: str, thumbnail: Path | None) -> dict[str, Any] | None:
    if thumbnail is None:
        return None
    *_, MediaFileUpload = load_google_libs()
    mime_type = mimetypes.guess_type(str(thumbnail))[0] or "image/png"
    media = MediaFileUpload(str(thumbnail), mimetype=mime_type, resumable=False)
    return youtube.thumbnails().set(videoId=video_id, media_body=media).execute()


def command_upload(args: argparse.Namespace) -> None:
    project_dir = normalize_project_dir(args.project_dir)
    paths = project_paths(project_dir)

    if paths["upload"].exists() and not args.force:
        print(f"upload_json_exists {paths['upload']}")
        print("not re-uploading; checking status instead")
        command_status(args)
        return

    video_path = paths["video"]
    if not video_path.exists():
        die(f"missing final video: {video_path}")

    metadata = read_json(paths["metadata"])
    body = metadata_body(metadata, args.visibility)
    thumbnail, thumbnail_warning, thumbnail_compression = select_thumbnail(
        project_dir,
        selected=args.thumbnail,
        quality=args.thumbnail_quality,
        scale_percent=args.thumbnail_scale_percent,
    )

    youtube = youtube_client("upload")
    *_, HttpError, MediaFileUpload = load_google_libs()
    media = MediaFileUpload(str(video_path), chunksize=1024 * 1024, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    try:
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"upload_progress {int(status.progress() * 100)}%")
    except HttpError as exc:
        payload = {
            "state": "failed",
            "operation": "upload",
            "failed_at": utc_now(),
            "project": str(project_dir),
            "video_path": str(video_path),
            "visibility": args.visibility,
            "error": str(exc),
            "status_code": getattr(exc.resp, "status", None),
        }
        out = write_upload_json(project_dir, payload)
        print(f"upload_failed {out}")
        raise

    video_id = response.get("id")
    if not video_id:
        die("YouTube upload response did not include a video id")

    thumbnail_response = None
    thumbnail_error = None
    if thumbnail is not None:
        try:
            thumbnail_response = upload_thumbnail(youtube, video_id, thumbnail)
        except Exception as exc:  # Keep video upload success even if thumbnail fails.
            thumbnail_error = str(exc)

    payload = {
        "state": "uploaded",
        "video_id": video_id,
        "url": video_url(video_id),
        "visibility": args.visibility,
        "processing_status": "unknown",
        "project": str(project_dir),
        "video_path": str(video_path),
        "video_sha256": sha256_file(video_path),
        "metadata_path": str(paths["metadata"]),
        "metadata_sha256": sha256_json(metadata),
        "thumbnail_path": str(thumbnail) if thumbnail else None,
        "thumbnail_sha256": sha256_file(thumbnail) if thumbnail else None,
        "thumbnail_warning": thumbnail_warning,
        "thumbnail_compression": thumbnail_compression,
        "thumbnail_error": thumbnail_error,
        "uploaded_at": utc_now(),
        "last_checked_at": None,
        "youtube_response": response,
        "thumbnail_response": thumbnail_response,
    }
    out = write_upload_json(project_dir, payload)
    print("upload_accepted True")
    print(f"video_id {video_id}")
    print(f"url {video_url(video_id)}")
    print(f"visibility {args.visibility}")
    print(f"saved {out}")
    if thumbnail_error:
        print(f"thumbnail_failed {thumbnail_error}")
    elif thumbnail:
        print(f"thumbnail_set {thumbnail}")
    else:
        print(f"thumbnail_skipped {thumbnail_warning}")


def command_status(args: argparse.Namespace) -> None:
    project_dir = normalize_project_dir(args.project_dir)
    paths = project_paths(project_dir)
    if not paths["upload"].exists():
        die(f"missing upload state: {paths['upload']}")

    payload = read_json(paths["upload"])
    video_id = payload.get("video_id")
    if not video_id:
        die(f"upload.json does not contain video_id: {paths['upload']}")

    youtube = youtube_client("manage")
    item = fetch_video_resource(youtube, video_id)
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


def command_list(args: argparse.Namespace) -> None:
    youtube = youtube_client("manage")
    uploads_playlist_id = (
        authenticated_channel(youtube)
        .get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads")
    )
    if not uploads_playlist_id:
        die("authenticated channel does not expose an uploads playlist")

    playlist_response = (
        youtube.playlistItems()
        .list(
            part="contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=args.max_results,
        )
        .execute()
    )
    video_ids = [
        item.get("contentDetails", {}).get("videoId")
        for item in playlist_response.get("items", [])
        if item.get("contentDetails", {}).get("videoId")
    ]

    if not video_ids:
        print("no uploads found")
        return

    videos_response = (
        youtube.videos()
        .list(
            part="snippet,status,statistics,contentDetails",
            id=",".join(video_ids),
            maxResults=args.max_results,
        )
        .execute()
    )
    items = videos_response.get("items", [])

    if args.json:
        print(json.dumps({"items": items}, indent=2, ensure_ascii=False))
        return

    print("video_id\tprivacy\tviews\tpublished_at\ttitle")
    for item in items:
        print_video_row(item)


def command_fetch(args: argparse.Namespace) -> None:
    video_id = parse_video_id(args.video)
    youtube = youtube_client("manage")
    item = fetch_video_resource(youtube, video_id)

    if args.project:
        project_dir = normalize_project_dir(args.project)
        paths = project_paths(project_dir)
        existing = read_json(paths["upload"]) if paths["upload"].exists() else None
        if existing and existing.get("video_id") and existing.get("video_id") != video_id and not args.force:
            die(
                f"{paths['upload']} already points to {existing.get('video_id')}; "
                "use --force to attach a different video"
            )
        payload = existing or {}
        payload.update(upload_state_from_video(project_dir, video_id, item))
        out = write_upload_json(project_dir, payload)
        print(f"video_id {video_id}")
        print(f"url {video_url(video_id)}")
        print(f"state {payload['state']}")
        print(f"saved {out}")
        return

    if args.json:
        print(json.dumps({"video_id": video_id, "item": item}, indent=2, ensure_ascii=False))
        return

    if not item:
        print(f"video_id {video_id}")
        print("state not_found")
        return

    print("video_id\tprivacy\tviews\tpublished_at\ttitle")
    print_video_row(item)


def command_compress_thumbnail(args: argparse.Namespace) -> None:
    project_dir = normalize_project_dir(args.project_dir)
    source, warning = resolve_thumbnail_path(project_dir, args.thumbnail)
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
    if out.stat().st_size > args.max_bytes:
        print("status over_limit")
    else:
        print("status ok")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload, check, list, or fetch YouTube videos.")
    sub = parser.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth", help="Authenticate or re-authenticate the YouTube channel.")
    auth.add_argument("--scope", choices=["upload", "manage", "both"], default="both")
    auth.add_argument("--reset", action="store_true", help="Delete stored token(s) before OAuth.")
    auth.set_defaults(func=command_auth)

    whoami = sub.add_parser("whoami", help="Show the currently authenticated YouTube channel.")
    whoami.add_argument("--scope", choices=["upload", "manage"], default="manage")
    whoami.add_argument("--json", action="store_true", help="Print raw channel JSON.")
    whoami.set_defaults(func=command_whoami)

    upload = sub.add_parser("upload", help="Upload the project video once and write upload.json.")
    upload.add_argument("project_dir", help="Path like library/<project_slug>")
    upload.add_argument("--visibility", choices=["private", "unlisted", "public"], default="private")
    upload.add_argument("--thumbnail", help="Thumbnail filename under youtube/thumbnails/ or explicit path.")
    upload.add_argument("--thumbnail-quality", type=int, default=88, help="JPEG quality percentage for auto-compression.")
    upload.add_argument("--thumbnail-scale-percent", type=int, default=100, help="Resize percentage for auto-compression.")
    upload.add_argument("--force", action="store_true", help="Force a new upload even if upload.json exists.")
    upload.set_defaults(func=command_upload)

    status = sub.add_parser("status", help="Check an existing upload and update upload.json.")
    status.add_argument("project_dir", help="Path like library/<project_slug>")
    status.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    status.set_defaults(func=command_status, visibility=None)

    list_cmd = sub.add_parser("list", help="List recent uploads for the authenticated channel.")
    list_cmd.add_argument("--max-results", type=int, default=10)
    list_cmd.add_argument("--json", action="store_true", help="Print raw JSON and write nothing.")
    list_cmd.set_defaults(func=command_list)

    fetch = sub.add_parser("fetch", help="Fetch one YouTube video by id or URL.")
    fetch.add_argument("video", help="YouTube video id or URL")
    fetch.add_argument("--project", help="Optional library/<project_slug> to attach/update upload.json")
    fetch.add_argument("--force", action="store_true", help="Allow replacing a different video_id in upload.json.")
    fetch.add_argument("--json", action="store_true", help="Print raw JSON and write nothing unless --project is used.")
    fetch.set_defaults(func=command_fetch)

    compress = sub.add_parser("compress-thumbnail", help="Compress a project thumbnail for YouTube upload.")
    compress.add_argument("project_dir", help="Path like library/<project_slug>")
    compress.add_argument("--thumbnail", required=True, help="Thumbnail filename under youtube/thumbnails/ or explicit path.")
    compress.add_argument("--quality", type=int, default=88, help="Starting JPEG quality percentage.")
    compress.add_argument("--scale-percent", type=int, default=100, help="Resize percentage; default preserves dimensions.")
    compress.add_argument("--max-bytes", type=int, default=THUMBNAIL_MAX_BYTES)
    compress.add_argument("--output", help="Optional output filename/path. Defaults to a sibling -youtube JPEG.")
    compress.set_defaults(func=command_compress_thumbnail)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
