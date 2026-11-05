"""Create an editable production project from the public generation template."""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Project name: lowercase letters, numbers, and hyphens")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.name):
        parser.error("Use lowercase letters, numbers, and hyphens for the project name")
    target = ROOT / "work" / args.name
    if target.exists():
        parser.error(f"Project already exists: {target}")
    shutil.copytree(ROOT / "examples" / "template", target)
    config_path = target / "scenes.json"
    config = json.loads(config_path.read_text())
    for scene in config["scenes"]:
        scene["output_path"] = str((target / "videos" / f"{scene['id']}.mp4").relative_to(ROOT))
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
