import os
from tavily import TavilyClient, AsyncTavilyClient

def load_env_keys():
    env_path = os.path.expanduser("~/.config/projects/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

def get_client():
    load_env_keys()
    if "TAVILY_API_KEY" not in os.environ:
        raise ValueError("TAVILY_API_KEY not found in environment or ~/.config/projects/.env")
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

def get_async_client():
    load_env_keys()
    if "TAVILY_API_KEY" not in os.environ:
        raise ValueError("TAVILY_API_KEY not found in environment or ~/.config/projects/.env")
    return AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
