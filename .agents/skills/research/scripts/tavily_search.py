import sys
import json
import argparse
from tavily_common import get_client

def main():
    parser = argparse.ArgumentParser(description="Run a Tavily web search")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--search-depth", choices=["basic", "advanced"], default="basic", help="Depth of search")
    parser.add_argument("--topic", choices=["general", "news", "finance"], default="general", help="Topic classification")
    parser.add_argument("--max-results", type=int, default=5, help="Maximum results to return")
    parser.add_argument("--include-raw-content", action="store_true", help="Include raw HTML content")
    args = parser.parse_args()

    try:
        client = get_client()
        response = client.search(
            query=args.query,
            search_depth=args.search_depth,
            topic=args.topic,
            max_results=args.max_results,
            include_raw_content=args.include_raw_content
        )
        print(json.dumps(response, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
