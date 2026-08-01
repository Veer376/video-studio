import os
import sys
import json
import argparse
import asyncio

# Add current folder to sys.path for direct imports
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from tavily_common import get_async_client

async def run_research(query, model):
    try:
        client = get_async_client()
        task = await client.research(input=query, model=model)
        request_id = task["request_id"]
        
        # Poll for status
        while True:
            result = await client.get_research(request_id)
            if result["status"] == "completed":
                return result
            elif result["status"] == "failed":
                raise RuntimeError("Research task failed")
            await asyncio.sleep(5)
    except Exception as e:
        raise e

def main():
    parser = argparse.ArgumentParser(description="Run an end-to-end research task using Tavily")
    parser.add_argument("--query", required=True, help="Research query or topic description")
    parser.add_argument("--model", choices=["mini", "standard"], default="mini", help="Model scale for research")
    args = parser.parse_args()

    try:
        result = asyncio.run(run_research(args.query, args.model))
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
