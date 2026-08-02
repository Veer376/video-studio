from __future__ import annotations

import json
from typing import Any

from .auth import authenticated_channel
from .common import die, parse_channel_handle, parse_video_id
from .transcript import command_transcript


VIDEO_PARTS = "snippet,status,processingDetails,statistics,contentDetails"


def fetch_video_resource(youtube, video_id: str) -> dict[str, Any] | None:
    response = youtube.videos().list(part=VIDEO_PARTS, id=video_id).execute()
    items = response.get("items", [])
    return items[0] if items else None


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


def command_search(args, youtube) -> None:
    response = (
        youtube.search()
        .list(
            part="snippet",
            q=args.query,
            type=args.type,
            maxResults=args.max_results,
            order=args.order,
            regionCode=args.region_code,
            relevanceLanguage=args.language,
            safeSearch=args.safe_search,
        )
        .execute()
    )
    if args.json:
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return

    print("kind\tid\tpublished_at\tchannel\ttitle")
    for item in response.get("items", []):
        kind = item.get("id", {}).get("kind", "").replace("youtube#", "")
        item_id = item.get("id", {}).get("videoId") or item.get("id", {}).get("channelId") or item.get("id", {}).get("playlistId")
        snippet = item.get("snippet", {})
        print(
            f"{kind}\t{item_id}\t{snippet.get('publishedAt', '')}\t"
            f"{snippet.get('channelTitle', '')}\t{snippet.get('title', '').replace(chr(10), ' ')[:90]}"
        )


def command_fetch(args, youtube) -> None:
    video_id = parse_video_id(args.video)
    item = fetch_video_resource(youtube, video_id)
    if args.json:
        print(json.dumps({"video_id": video_id, "item": item}, indent=2, ensure_ascii=False))
        return
    if not item:
        print(f"video_id {video_id}")
        print("state not_found")
        return
    print("video_id\tprivacy\tviews\tpublished_at\ttitle")
    print_video_row(item)


def command_list(args, youtube) -> None:
    uploads_playlist_id = (
        authenticated_channel(youtube)
        .get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads")
    )
    if not uploads_playlist_id:
        die("authenticated channel does not expose an uploads playlist")
    args.playlist_id = uploads_playlist_id
    command_playlist(args, youtube)


def command_channel(args, youtube) -> None:
    value = parse_channel_handle(args.channel)
    request = youtube.channels().list(part="id,snippet,statistics,contentDetails,status", id=value)
    if value.startswith("@"):
        request = youtube.channels().list(part="id,snippet,statistics,contentDetails,status", forHandle=value)
    response = request.execute()
    if args.json:
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return
    items = response.get("items", [])
    if not items:
        print("state not_found")
        return
    channel = items[0]
    snippet = channel.get("snippet", {})
    stats = channel.get("statistics", {})
    print(f"channel_id {channel.get('id')}")
    print(f"title {snippet.get('title')}")
    print(f"custom_url {snippet.get('customUrl', '')}")
    print(f"subscribers {stats.get('subscriberCount', '')}")
    print(f"videos {stats.get('videoCount', '')}")
    print(f"views {stats.get('viewCount', '')}")


def command_playlist(args, youtube) -> None:
    response = (
        youtube.playlistItems()
        .list(part="snippet,contentDetails", playlistId=args.playlist_id, maxResults=args.max_results)
        .execute()
    )
    if args.json:
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return
    print("video_id\tpublished_at\tchannel\ttitle")
    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        video_id = item.get("contentDetails", {}).get("videoId", "")
        print(
            f"{video_id}\t{snippet.get('publishedAt', '')}\t"
            f"{snippet.get('videoOwnerChannelTitle') or snippet.get('channelTitle', '')}\t"
            f"{snippet.get('title', '').replace(chr(10), ' ')[:90]}"
        )


def command_comments(args, youtube) -> None:
    video_id = parse_video_id(args.video)
    response = (
        youtube.commentThreads()
        .list(
            part="snippet,replies",
            videoId=video_id,
            maxResults=args.max_results,
            order=args.order,
            textFormat="plainText",
        )
        .execute()
    )
    if args.json:
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return
    print("published_at\tlikes\tauthor\ttext")
    for item in response.get("items", []):
        top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        text = top.get("textDisplay", "").replace("\n", " ")[:180]
        print(f"{top.get('publishedAt', '')}\t{top.get('likeCount', '')}\t{top.get('authorDisplayName', '')}\t{text}")

