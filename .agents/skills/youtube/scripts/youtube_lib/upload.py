from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from .common import die, load_google_libs, sha256_file, utc_now, video_url
from .media import ensure_uploadable_thumbnail


def metadata_body(
    *,
    title: str,
    description: str,
    visibility: str,
    tags: list[str] | None = None,
    category_id: str = "22",
    made_for_kids: bool = False,
) -> dict[str, Any]:
    if not title:
        die("title is required")
    snippet: dict[str, Any] = {
        "title": title[:100],
        "description": description[:5000],
        "categoryId": str(category_id),
    }
    if tags:
        snippet["tags"] = [str(t) for t in tags][:30]
    return {
        "snippet": snippet,
        "status": {
            "privacyStatus": visibility,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }


def upload_thumbnail(youtube, video_id: str, thumbnail: Path | None) -> dict[str, Any] | None:
    if thumbnail is None:
        return None
    *_, MediaFileUpload = load_google_libs()
    mime_type = mimetypes.guess_type(str(thumbnail))[0] or "image/png"
    media = MediaFileUpload(str(thumbnail), mimetype=mime_type, resumable=False)
    return youtube.thumbnails().set(videoId=video_id, media_body=media).execute()


def upload_file(
    youtube,
    *,
    video_path: Path,
    title: str,
    description: str,
    visibility: str,
    thumbnail: Path | None = None,
    tags: list[str] | None = None,
    category_id: str = "22",
    made_for_kids: bool = False,
    thumbnail_quality: int = 88,
    thumbnail_scale_percent: int = 100,
) -> dict[str, Any]:
    if not video_path.exists() or not video_path.is_file():
        die(f"video file does not exist: {video_path}")

    thumbnail_path, thumbnail_warning, thumbnail_compression = ensure_uploadable_thumbnail(
        thumbnail,
        quality=thumbnail_quality,
        scale_percent=thumbnail_scale_percent,
    )

    body = metadata_body(
        title=title,
        description=description,
        visibility=visibility,
        tags=tags,
        category_id=category_id,
        made_for_kids=made_for_kids,
    )

    *_, HttpError, MediaFileUpload = load_google_libs()
    media = MediaFileUpload(str(video_path), chunksize=1024 * 1024, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    try:
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"upload_progress {int(status.progress() * 100)}%")
    except HttpError:
        raise

    video_id = response.get("id")
    if not video_id:
        die("YouTube upload response did not include a video id")

    thumbnail_response = None
    thumbnail_error = None
    if thumbnail_path is not None:
        try:
            thumbnail_response = upload_thumbnail(youtube, video_id, thumbnail_path)
        except Exception as exc:
            thumbnail_error = str(exc)

    return {
        "state": "uploaded",
        "video_id": video_id,
        "url": video_url(video_id),
        "visibility": visibility,
        "processing_status": "unknown",
        "video_path": str(video_path),
        "video_sha256": sha256_file(video_path),
        "thumbnail_path": str(thumbnail_path) if thumbnail_path else None,
        "thumbnail_sha256": sha256_file(thumbnail_path) if thumbnail_path else None,
        "thumbnail_warning": thumbnail_warning,
        "thumbnail_compression": thumbnail_compression,
        "thumbnail_error": thumbnail_error,
        "uploaded_at": utc_now(),
        "last_checked_at": None,
        "youtube_response": response,
        "thumbnail_response": thumbnail_response,
    }


def print_upload_result(payload: dict[str, Any]) -> None:
    print("upload_accepted True")
    print(f"video_id {payload.get('video_id')}")
    print(f"url {payload.get('url')}")
    print(f"visibility {payload.get('visibility')}")
    if payload.get("thumbnail_error"):
        print(f"thumbnail_failed {payload.get('thumbnail_error')}")
    elif payload.get("thumbnail_path"):
        print(f"thumbnail_set {payload.get('thumbnail_path')}")
    elif payload.get("thumbnail_warning"):
        print(f"thumbnail_skipped {payload.get('thumbnail_warning')}")
