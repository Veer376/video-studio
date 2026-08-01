#!/usr/bin/env python3
"""Fetch YouTube Analytics for Story Video Maker projects.

This script intentionally lives inside the youtube-analytics skill. It does not
depend on project src/ code so analytics remains skill-owned.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ANALYTICS_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def die(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_google_libs() -> tuple[Any, Any, Any, Any]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ModuleNotFoundError:
        die(
            "missing Google API libraries. Install with: "
            "python3 -m pip install --user google-api-python-client "
            "google-auth-oauthlib google-auth-httplib2"
        )
    return Request, Credentials, InstalledAppFlow, build


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


def video_url(video_id: str) -> str:
    return f"https://youtu.be/{video_id}"


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"missing required file: {path}")
    except json.JSONDecodeError as exc:
        die(f"invalid JSON in {path}: {exc}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def normalize_project_dir(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.exists():
        die(f"project folder does not exist: {p}")
    if not p.is_dir():
        die(f"project path is not a folder: {p}")
    return p


def project_video_id(project_dir: Path) -> str:
    upload_path = project_dir / "youtube" / "upload.json"
    upload = read_json(upload_path)
    video_id = upload.get("video_id")
    if not video_id:
        die(f"{upload_path} does not contain video_id")
    return str(video_id)


def default_dates(days: int) -> tuple[str, str]:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=max(days, 1) - 1)
    return start.isoformat(), end.isoformat()


def resolved_dates(args: argparse.Namespace) -> tuple[str, str]:
    start, end = default_dates(args.days)
    return args.start_date or start, args.end_date or end


def get_credentials():
    Request, Credentials, InstalledAppFlow, _ = load_google_libs()
    config_dir = Path.home() / ".config" / "projects"
    client_secret = config_dir / "youtube_client_secret.json"
    token_path = config_dir / "youtube_analytics_token.json"
    if not client_secret.exists():
        die(f"missing OAuth client secret: {client_secret}")

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), ANALYTICS_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), ANALYTICS_SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True, prompt="consent")
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def analytics_client():
    *_, build = load_google_libs()
    return build("youtubeAnalytics", "v2", credentials=get_credentials())


def table_to_records(table: dict[str, Any]) -> list[dict[str, Any]]:
    headers = [h["name"] for h in table.get("columnHeaders", [])]
    return [dict(zip(headers, row)) for row in table.get("rows", [])]


def query_report(
    client,
    *,
    start_date: str,
    end_date: str,
    metrics: str,
    dimensions: str | None = None,
    filters: str | None = None,
    sort: str | None = None,
    max_results: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "ids": "channel==MINE",
        "startDate": start_date,
        "endDate": end_date,
        "metrics": metrics,
    }
    if dimensions:
        params["dimensions"] = dimensions
    if filters:
        params["filters"] = filters
    if sort:
        params["sort"] = sort
    if max_results:
        params["maxResults"] = max_results
    table = client.reports().query(**params).execute()
    return {
        "query": params,
        "column_headers": table.get("columnHeaders", []),
        "rows": table.get("rows", []),
        "records": table_to_records(table),
    }


def safe_query(client, name: str, **kwargs: Any) -> dict[str, Any]:
    try:
        result = query_report(client, **kwargs)
        result["ok"] = True
        return result
    except Exception as exc:
        return {
            "ok": False,
            "query": kwargs,
            "error": str(exc),
            "records": [],
            "rows": [],
            "column_headers": [],
        }


def build_video_reports(client, video_id: str, start_date: str, end_date: str) -> dict[str, Any]:
    filters = f"video=={video_id}"
    return {
        "overview": safe_query(
            client,
            "overview",
            start_date=start_date,
            end_date=end_date,
            metrics=(
                "views,estimatedMinutesWatched,averageViewDuration,"
                "averageViewPercentage,likes,comments,shares,subscribersGained,subscribersLost"
            ),
            filters=filters,
        ),
        "daily": safe_query(
            client,
            "daily",
            start_date=start_date,
            end_date=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
            dimensions="day",
            filters=filters,
            sort="day",
        ),
        "retention": safe_query(
            client,
            "retention",
            start_date=start_date,
            end_date=end_date,
            metrics="audienceWatchRatio,relativeRetentionPerformance",
            dimensions="elapsedVideoTimeRatio",
            filters=filters,
            sort="elapsedVideoTimeRatio",
        ),
        "traffic_sources": safe_query(
            client,
            "traffic_sources",
            start_date=start_date,
            end_date=end_date,
            metrics="views,estimatedMinutesWatched",
            dimensions="insightTrafficSourceType",
            filters=filters,
            sort="-views",
            max_results=25,
        ),
        "countries": safe_query(
            client,
            "countries",
            start_date=start_date,
            end_date=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration",
            dimensions="country",
            filters=filters,
            sort="-views",
            max_results=25,
        ),
        "devices": safe_query(
            client,
            "devices",
            start_date=start_date,
            end_date=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration",
            dimensions="deviceType",
            filters=filters,
            sort="-views",
            max_results=25,
        ),
    }


def retention_insights(report: dict[str, Any]) -> dict[str, Any]:
    records = report.get("records", [])
    points = [
        {
            "elapsedVideoTimeRatio": r.get("elapsedVideoTimeRatio"),
            "audienceWatchRatio": r.get("audienceWatchRatio"),
            "relativeRetentionPerformance": r.get("relativeRetentionPerformance"),
        }
        for r in records
        if r.get("audienceWatchRatio") is not None
    ]
    if not points:
        return {"available": False}

    min_point = min(points, key=lambda p: p.get("audienceWatchRatio") or 0)
    first_below_half = next((p for p in points if (p.get("audienceWatchRatio") or 0) < 0.5), None)
    largest_drop = None
    for prev, cur in zip(points, points[1:]):
        drop = (prev.get("audienceWatchRatio") or 0) - (cur.get("audienceWatchRatio") or 0)
        if largest_drop is None or drop > largest_drop["drop"]:
            largest_drop = {"from": prev, "to": cur, "drop": drop}

    return {
        "available": True,
        "points": len(points),
        "lowest_point": min_point,
        "first_below_50_percent": first_below_half,
        "largest_drop": largest_drop,
    }


def package_video_payload(project_dir: Path | None, video_id: str, start_date: str, end_date: str) -> dict[str, Any]:
    client = analytics_client()
    reports = build_video_reports(client, video_id, start_date, end_date)
    return {
        "fetched_at": utc_now(),
        "project": str(project_dir) if project_dir else None,
        "video_id": video_id,
        "url": video_url(video_id),
        "date_range": {"start_date": start_date, "end_date": end_date},
        "reports": reports,
        "insights": {
            "retention": retention_insights(reports["retention"]),
            "reports_with_no_rows": [
                name for name, report in reports.items() if report.get("ok") and not report.get("records")
            ],
            "failed_reports": [
                {"name": name, "error": report.get("error")}
                for name, report in reports.items()
                if not report.get("ok")
            ],
        },
    }


def print_summary(payload: dict[str, Any]) -> None:
    overview = payload.get("reports", {}).get("overview", {}).get("records", [])
    row = overview[0] if overview else {}
    print(f"video_id {payload.get('video_id')}")
    print(f"url {payload.get('url')}")
    print(f"range {payload['date_range']['start_date']}..{payload['date_range']['end_date']}")
    for key in ("views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage", "likes", "comments"):
        if key in row:
            print(f"{key} {row[key]}")
    retention = payload.get("insights", {}).get("retention", {})
    print(f"retention_available {retention.get('available', False)}")
    failed = payload.get("insights", {}).get("failed_reports", [])
    if failed:
        print(f"failed_reports {len(failed)}")


def command_fetch(args: argparse.Namespace) -> None:
    project_dir = normalize_project_dir(args.project_dir)
    video_id = project_video_id(project_dir)
    start_date, end_date = resolved_dates(args)
    payload = package_video_payload(project_dir, video_id, start_date, end_date)
    out = project_dir / "youtube" / "analytics.json"
    write_json(out, payload)
    print_summary(payload)
    print(f"saved {out}")


def command_video(args: argparse.Namespace) -> None:
    project_dir = normalize_project_dir(args.project) if args.project else None
    video_id = parse_video_id(args.video)
    start_date, end_date = resolved_dates(args)
    payload = package_video_payload(project_dir, video_id, start_date, end_date)
    if project_dir:
        out = project_dir / "youtube" / "analytics.json"
        write_json(out, payload)
        print_summary(payload)
        print(f"saved {out}")
    elif args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print_summary(payload)


def command_channel(args: argparse.Namespace) -> None:
    client = analytics_client()
    start_date, end_date = resolved_dates(args)
    reports = {
        "overview": safe_query(
            client,
            "overview",
            start_date=start_date,
            end_date=end_date,
            metrics=(
                "views,estimatedMinutesWatched,averageViewDuration,"
                "averageViewPercentage,likes,comments,shares,subscribersGained,subscribersLost"
            ),
        ),
        "daily": safe_query(
            client,
            "daily",
            start_date=start_date,
            end_date=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
            dimensions="day",
            sort="day",
        ),
        "top_videos": safe_query(
            client,
            "top_videos",
            start_date=start_date,
            end_date=end_date,
            metrics="views,estimatedMinutesWatched,averageViewDuration",
            dimensions="video",
            sort="-views",
            max_results=args.max_results,
        ),
        "traffic_sources": safe_query(
            client,
            "traffic_sources",
            start_date=start_date,
            end_date=end_date,
            metrics="views,estimatedMinutesWatched",
            dimensions="insightTrafficSourceType",
            sort="-views",
            max_results=25,
        ),
    }
    payload = {
        "fetched_at": utc_now(),
        "date_range": {"start_date": start_date, "end_date": end_date},
        "reports": reports,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"range {start_date}..{end_date}")
    overview = reports["overview"].get("records", [])
    if overview:
        for key, value in overview[0].items():
            print(f"{key} {value}")
    print("top_videos")
    for row in reports["top_videos"].get("records", [])[: args.max_results]:
        print(f"{row.get('video')}\t{row.get('views')}\t{row.get('estimatedMinutesWatched')}")


def command_query(args: argparse.Namespace) -> None:
    client = analytics_client()
    start_date, end_date = resolved_dates(args)
    result = query_report(
        client,
        start_date=start_date,
        end_date=end_date,
        metrics=args.metrics,
        dimensions=args.dimensions,
        filters=args.filters,
        sort=args.sort,
        max_results=args.max_results,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


def add_date_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--days", type=int, default=28)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch YouTube Analytics reports.")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Fetch analytics for a project and write youtube/analytics.json.")
    fetch.add_argument("project_dir", help="Path like library/<project_slug>")
    add_date_args(fetch)
    fetch.set_defaults(func=command_fetch)

    video = sub.add_parser("video", help="Fetch analytics for one YouTube video id or URL.")
    video.add_argument("video", help="YouTube video id or URL")
    video.add_argument("--project", help="Optional project folder to write youtube/analytics.json")
    video.add_argument("--json", action="store_true")
    add_date_args(video)
    video.set_defaults(func=command_video)

    channel = sub.add_parser("channel", help="Print channel-level analytics summary.")
    channel.add_argument("--max-results", type=int, default=10)
    channel.add_argument("--json", action="store_true")
    add_date_args(channel)
    channel.set_defaults(func=command_channel)

    query = sub.add_parser("query", help="Run a raw YouTube Analytics reports.query call.")
    query.add_argument("--metrics", required=True)
    query.add_argument("--dimensions")
    query.add_argument("--filters")
    query.add_argument("--sort")
    query.add_argument("--max-results", type=int)
    add_date_args(query)
    query.set_defaults(func=command_query)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
