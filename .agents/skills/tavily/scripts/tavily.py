#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Remove the script's directory from sys.path to avoid name collision with the tavily library
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p) != script_dir]


def load_env() -> None:
    env_path = Path.home() / ".config/projects/.env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_client():
    load_env()
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not found in environment or ~/.config/projects/.env")
    from tavily import TavilyClient

    return TavilyClient(api_key=api_key)


def get_async_client():
    load_env()
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not found in environment or ~/.config/projects/.env")
    from tavily import AsyncTavilyClient

    return AsyncTavilyClient(api_key=api_key)


def write_result(result, out_path: str | None) -> None:
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if out_path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(str(path))
    else:
        print(text)


def cmd_search(args):
    client = get_client()
    return client.search(
        query=args.query,
        search_depth=args.search_depth,
        topic=args.topic,
        max_results=args.max_results,
        include_raw_content=args.include_raw_content,
    )


def cmd_extract(args):
    client = get_client()
    urls = [url.strip() for url in args.urls.split(",") if url.strip()]
    if not urls:
        raise RuntimeError("--urls must include at least one URL")
    return client.extract(urls=urls)


def cmd_map(args):
    client = get_client()
    return client.map(url=args.url)


def cmd_crawl(args):
    client = get_client()
    return client.crawl(url=args.url, max_depth=args.max_depth, max_pages=args.max_pages)


async def run_research(args):
    client = get_async_client()
    task = await client.research(input=args.query, model=args.model)
    request_id = task["request_id"]

    for _ in range(args.max_polls):
        result = await client.get_research(request_id)
        status = result.get("status")
        if status == "completed":
            return result
        if status == "failed":
            raise RuntimeError(f"Tavily research failed: {json.dumps(result, ensure_ascii=False)}")
        await asyncio.sleep(args.poll_interval)

    raise TimeoutError(f"Tavily research did not complete after {args.max_polls} polls")


def build_parser():
    parser = argparse.ArgumentParser(description="Shared Tavily CLI for search, extraction, crawl, map, and research")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Run Tavily web search")
    search.add_argument("--query", required=True)
    search.add_argument("--search-depth", choices=["basic", "advanced"], default="basic")
    search.add_argument("--topic", choices=["general", "news", "finance"], default="general")
    search.add_argument("--max-results", type=int, default=5)
    search.add_argument("--include-raw-content", action="store_true")
    search.add_argument("--out")

    extract = sub.add_parser("extract", help="Extract clean content from one or more URLs")
    extract.add_argument("--urls", required=True, help="Comma-separated URLs")
    extract.add_argument("--out")

    map_parser = sub.add_parser("map", help="Map a site and return discovered URLs")
    map_parser.add_argument("--url", required=True)
    map_parser.add_argument("--out")

    crawl = sub.add_parser("crawl", help="Crawl a site and extract bounded content")
    crawl.add_argument("--url", required=True)
    crawl.add_argument("--max-depth", type=int, default=1)
    crawl.add_argument("--max-pages", type=int, default=5)
    crawl.add_argument("--out")

    research = sub.add_parser("research", help="Run async Tavily deep research")
    research.add_argument("--query", required=True)
    research.add_argument("--model", choices=["mini", "standard"], default="mini")
    research.add_argument("--poll-interval", type=float, default=5.0)
    research.add_argument("--max-polls", type=int, default=120)
    research.add_argument("--out")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "search":
            result = cmd_search(args)
        elif args.command == "extract":
            result = cmd_extract(args)
        elif args.command == "map":
            result = cmd_map(args)
        elif args.command == "crawl":
            result = cmd_crawl(args)
        elif args.command == "research":
            result = asyncio.run(run_research(args))
        else:
            parser.error(f"unknown command: {args.command}")
        write_result(result, args.out)
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
