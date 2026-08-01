import sys
import json
import argparse
from tavily_common import get_client

def main():
    parser = argparse.ArgumentParser(description="Extract clean content from URLs using Tavily")
    parser.add_argument("--urls", required=True, help="Comma-separated list of URLs to extract content from")
    args = parser.parse_args()

    urls_list = [u.strip() for u in args.urls.split(",") if u.strip()]

    try:
        client = get_client()
        response = client.extract(urls=urls_list)
        print(json.dumps(response, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
