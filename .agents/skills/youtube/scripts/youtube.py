#!/usr/bin/env python3
"""Generic YouTube API CLI for the youtube skill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from youtube_lib import data
from youtube_lib.auth import authenticated_channel, print_channel, reset_tokens, youtube_client
from youtube_lib.upload import print_upload_result, upload_file


def command_auth(args: argparse.Namespace) -> None:
    scope_profiles = ["upload", "manage", "readonly"] if args.scope == "all" else [args.scope]
    if args.reset:
        removed = reset_tokens(scope_profiles)
        if removed:
            for token in removed:
                print(f"removed {token}")
        else:
            print("removed none")

    for scope_profile in scope_profiles:
        youtube_client(scope_profile)
        print(f"authenticated {scope_profile}")

    profile = "manage" if "manage" in scope_profiles else scope_profiles[0]
    print_channel(authenticated_channel(youtube_client(profile)))


def command_whoami(args: argparse.Namespace) -> None:
    youtube = youtube_client(args.scope)
    channel = authenticated_channel(youtube)
    if args.json:
        print(json.dumps({"channel": channel}, indent=2, ensure_ascii=False))
        return
    print_channel(channel)


def command_upload_file(args: argparse.Namespace) -> None:
    tags = args.tag or []
    payload = upload_file(
        youtube_client("upload"),
        video_path=Path(args.video).expanduser(),
        title=args.title,
        description=args.description or "",
        visibility=args.visibility,
        thumbnail=Path(args.thumbnail).expanduser() if args.thumbnail else None,
        tags=tags,
        category_id=args.category_id,
        made_for_kids=args.made_for_kids,
        thumbnail_quality=args.thumbnail_quality,
        thumbnail_scale_percent=args.thumbnail_scale_percent,
    )
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print_upload_result(payload)


def command_search_router(args: argparse.Namespace) -> None:
    data.command_search(args, youtube_client("readonly"))


def command_fetch_router(args: argparse.Namespace) -> None:
    data.command_fetch(args, youtube_client("manage"))


def command_list_router(args: argparse.Namespace) -> None:
    data.command_list(args, youtube_client("manage"))


def command_channel_router(args: argparse.Namespace) -> None:
    data.command_channel(args, youtube_client("readonly"))


def command_playlist_router(args: argparse.Namespace) -> None:
    data.command_playlist(args, youtube_client("readonly"))


def command_comments_router(args: argparse.Namespace) -> None:
    data.command_comments(args, youtube_client("readonly"))


def command_transcript_router(args: argparse.Namespace) -> None:
    data.command_transcript(args, youtube_client("readonly"))


def add_upload_file_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("video", help="Local video file path.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--thumbnail", help="Optional local thumbnail path.")
    parser.add_argument("--visibility", choices=["private", "unlisted", "public"], default="private")
    parser.add_argument("--tag", action="append", help="Repeat for each tag.")
    parser.add_argument("--category-id", default="22")
    parser.add_argument("--made-for-kids", action="store_true")
    parser.add_argument("--thumbnail-quality", type=int, default=88)
    parser.add_argument("--thumbnail-scale-percent", type=int, default=100)
    parser.add_argument("--json", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YouTube API utility for auth, data lookup, and generic upload.")
    sub = parser.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth", help="Authenticate or re-authenticate a YouTube scope.")
    auth.add_argument("--scope", choices=["upload", "manage", "readonly", "all"], default="all")
    auth.add_argument("--reset", action="store_true")
    auth.set_defaults(func=command_auth)

    whoami = sub.add_parser("whoami", help="Show the currently authenticated YouTube channel.")
    whoami.add_argument("--scope", choices=["upload", "manage", "readonly"], default="manage")
    whoami.add_argument("--json", action="store_true")
    whoami.set_defaults(func=command_whoami)

    search = sub.add_parser("search", help="Search public YouTube data.")
    search.add_argument("query")
    search.add_argument("--type", choices=["video", "channel", "playlist"], default="video")
    search.add_argument("--order", choices=["date", "rating", "relevance", "title", "videoCount", "viewCount"], default="relevance")
    search.add_argument("--max-results", type=int, default=10)
    search.add_argument("--region-code", default="IN")
    search.add_argument("--language", default="hi")
    search.add_argument("--safe-search", choices=["moderate", "none", "strict"], default="moderate")
    search.add_argument("--json", action="store_true")
    search.set_defaults(func=command_search_router)

    fetch = sub.add_parser("fetch", help="Fetch one YouTube video by id or URL.")
    fetch.add_argument("video")
    fetch.add_argument("--processing-details", action="store_true", help="Request owner-only processingDetails and fall back to public parts if blocked.")
    fetch.add_argument("--json", action="store_true")
    fetch.set_defaults(func=command_fetch_router)

    channel = sub.add_parser("channel", help="Fetch a channel by id or @handle.")
    channel.add_argument("channel")
    channel.add_argument("--json", action="store_true")
    channel.set_defaults(func=command_channel_router)

    playlist = sub.add_parser("playlist", help="List videos in a playlist.")
    playlist.add_argument("playlist_id")
    playlist.add_argument("--max-results", type=int, default=10)
    playlist.add_argument("--json", action="store_true")
    playlist.set_defaults(func=command_playlist_router)

    comments = sub.add_parser("comments", help="Fetch top-level comments for a video.")
    comments.add_argument("video")
    comments.add_argument("--max-results", type=int, default=20)
    comments.add_argument("--order", choices=["time", "relevance"], default="relevance")
    comments.add_argument("--json", action="store_true")
    comments.set_defaults(func=command_comments_router)

    transcript = sub.add_parser("transcript", help="Fetch public transcript text with official caption-track lookup first.")
    transcript.add_argument("video")
    transcript.add_argument("--language", action="append", help="Preferred transcript language; repeatable. Defaults to hi then en.")
    transcript.add_argument("--no-fallback", action="store_true", help="Do not use public player transcript fallback.")
    transcript.add_argument("--json", action="store_true")
    transcript.set_defaults(func=command_transcript_router)

    upload_file_cmd = sub.add_parser("upload-file", help="Upload any local video file.")
    add_upload_file_args(upload_file_cmd)
    upload_file_cmd.set_defaults(func=command_upload_file)

    list_cmd = sub.add_parser("list", help="List recent uploads for the authenticated channel.")
    list_cmd.add_argument("--max-results", type=int, default=10)
    list_cmd.add_argument("--json", action="store_true")
    list_cmd.set_defaults(func=command_list_router)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
