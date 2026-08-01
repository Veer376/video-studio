import sys
import json
import argparse
from tavily_common import get_client

def main():
    parser = argparse.ArgumentParser(description="Crawl or map a site using Tavily")
    parser.add_argument("--url", required=True, help="URL of the site to crawl or map")
    parser.add_argument("--mode", choices=["crawl", "map"], default="crawl", help="Operation mode")
    parser.add_argument("--max-depth", type=int, default=1, help="Max recursion depth for crawl")
    parser.add_argument("--max-pages", type=int, default=5, help="Max pages to extract content from")
    args = parser.parse_args()

    try:
        client = get_client()
        if args.mode == "map":
            response = client.map(url=args.url)
        else:
            response = client.crawl(
                url=args.url,
                max_depth=args.max_depth,
                max_pages=args.max_pages
            )
        print(json.dumps(response, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
