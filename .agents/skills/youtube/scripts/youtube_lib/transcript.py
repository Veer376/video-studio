from __future__ import annotations

import json
from typing import Any

from .common import parse_video_id


def official_caption_tracks(youtube, video_id: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = youtube.captions().list(part="id,snippet", videoId=video_id).execute()
        return response, None
    except Exception as exc:
        return None, str(exc)


def normalize_segment(segment: Any) -> dict[str, Any]:
    if isinstance(segment, dict):
        return {
            "start": float(segment.get("start", 0.0)),
            "duration": float(segment.get("duration", 0.0)),
            "text": str(segment.get("text", "")).replace("\n", " ").strip(),
        }
    return {
        "start": float(getattr(segment, "start", 0.0)),
        "duration": float(getattr(segment, "duration", 0.0)),
        "text": str(getattr(segment, "text", "")).replace("\n", " ").strip(),
    }


def public_player_transcript(video_id: str, languages: list[str]) -> dict[str, Any]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "missing youtube-transcript-api. Install with: "
            "python3 -m pip install --user youtube-transcript-api"
        ) from exc

    api = YouTubeTranscriptApi()
    fetched = api.fetch(video_id, languages=languages)
    segments = [normalize_segment(segment) for segment in fetched]
    language = getattr(fetched, "language_code", None) or (languages[0] if languages else None)
    return {
        "source": "public_player_fallback",
        "language": language,
        "segments": segments,
        "text": " ".join(segment["text"] for segment in segments if segment["text"]),
    }


def command_transcript(args, youtube) -> None:
    video_id = parse_video_id(args.video)
    official_response, official_error = official_caption_tracks(youtube, video_id)
    languages = args.language or ["hi", "en"]

    fallback_payload: dict[str, Any] | None = None
    fallback_error: str | None = None
    if not args.no_fallback:
        try:
            fallback_payload = public_player_transcript(video_id, languages)
        except Exception as exc:
            fallback_error = str(exc)

    payload = {
        "video_id": video_id,
        "official_api": {
            "source": "official_api",
            "response": official_response,
            "error": official_error,
        },
        "fallback": fallback_payload,
        "fallback_error": fallback_error,
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if fallback_payload:
        print(f"video_id {video_id}")
        print("source public_player_fallback")
        print(f"language {fallback_payload.get('language')}")
        print(f"segments {len(fallback_payload.get('segments', []))}")
        print(f"text {fallback_payload.get('text', '')}")
        if official_error:
            print(f"official_api_error {official_error[:240]}")
        return

    print(f"video_id {video_id}")
    if official_response and official_response.get("items"):
        print("source official_api")
        print("caption_id\tlanguage\tname\ttrack_kind")
        for item in official_response.get("items", []):
            snippet = item.get("snippet", {})
            print(
                f"{item.get('id')}\t{snippet.get('language')}\t"
                f"{snippet.get('name', '')}\t{snippet.get('trackKind', '')}"
            )
        return

    print("state transcript_unavailable")
    if official_error:
        print(f"official_api_error {official_error[:240]}")
    if fallback_error:
        print(f"fallback_error {fallback_error[:240]}")
