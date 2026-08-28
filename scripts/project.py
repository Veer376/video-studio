#!/usr/bin/env python3
"""Create canonical video-project directories and initial artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "gemini-omni-flash-preview"
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProjectSetupError(ValueError):
    """Raised when a video project cannot be initialized safely."""


def derive_slug(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    if not slug:
        raise ProjectSetupError(
            "Could not derive an ASCII slug from the title; provide --slug explicitly"
        )
    return slug


def validate_slug(slug: str) -> str:
    candidate = slug.strip()
    if not SLUG_PATTERN.fullmatch(candidate):
        raise ProjectSetupError(
            "Slug must contain lowercase ASCII letters, numbers, and single hyphens"
        )
    return candidate


def initial_story(title: str) -> str:
    return f"""# {title}

Status: initialized — story planning pending.

## Premise and audience

<!-- Define the core premise, intended audience, and intended experience. -->

## Creative contract

- Format:
- Pacing:
- Dialogue:
- Visuals:
- Audio:
- Continuity:

## Story-writing instructions

- Target runtime:
- Clip duration:
- Part construction:
- Clip progression:
- Overload rule:

## Recurring story elements

- Main characters:
- Locations:
- Objects or motifs:

## Macro structure

| Time | Clips | Major event | Continuity or recurring hook |
|---|---:|---|---|

<!-- Add approved parts and sequential clip briefs during story planning. -->
"""


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def create_project(
    project_root: Path,
    *,
    title: str,
    aspect_ratio: str,
    slug: str | None = None,
) -> dict[str, Any]:
    clean_title = title.strip()
    if not clean_title or "\n" in clean_title or "\r" in clean_title:
        raise ProjectSetupError("Title must be one non-empty line")
    if aspect_ratio not in {"16:9", "9:16"}:
        raise ProjectSetupError("Aspect ratio must be 16:9 or 9:16")

    project_slug = validate_slug(slug) if slug is not None else derive_slug(clean_title)
    projects_root = project_root.resolve() / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)
    destination = projects_root / project_slug
    if destination.exists():
        raise ProjectSetupError(f"Project already exists: {destination}")

    staging = Path(
        tempfile.mkdtemp(prefix=f".{project_slug}.tmp-", dir=projects_root)
    )
    try:
        for relative in (
            "assets",
            "videos",
            "reviews",
            "temp/continuity_frames",
            "temp/contact_sheets",
            "output",
        ):
            (staging / relative).mkdir(parents=True, exist_ok=False)

        (staging / "story.md").write_text(
            initial_story(clean_title), encoding="utf-8"
        )
        _write_json(staging / "characters.json", {"characters": []})
        _write_json(
            staging / "scenes.json",
            {
                "model": DEFAULT_MODEL,
                "aspect_ratio": aspect_ratio,
                "characters_file": f"projects/{project_slug}/characters.json",
                "scenes": [],
            },
        )

        # Validate the staged artifacts before publishing the directory.
        characters = json.loads((staging / "characters.json").read_text(encoding="utf-8"))
        scenes = json.loads((staging / "scenes.json").read_text(encoding="utf-8"))
        if characters != {"characters": []} or scenes.get("scenes") != []:
            raise ProjectSetupError("Staged project artifacts failed validation")

        if destination.exists():
            raise ProjectSetupError(f"Project already exists: {destination}")
        os.rename(staging, destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    relative = destination.relative_to(project_root.resolve())
    return {
        "status": "created",
        "project": {
            "title": clean_title,
            "slug": project_slug,
            "path": str(destination.resolve()),
            "relative_path": str(relative),
            "aspect_ratio": aspect_ratio,
            "model": DEFAULT_MODEL,
        },
        "artifacts": {
            "story": str(relative / "story.md"),
            "characters": str(relative / "characters.json"),
            "scenes": str(relative / "scenes.json"),
        },
        "next_action": "plan_story",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="project",
        description="Manage canonical video projects.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser(
        "create", help="Create an initialized project under projects/"
    )
    create.add_argument("--title", required=True, help="Human-readable story title")
    create.add_argument(
        "--aspect-ratio",
        required=True,
        choices=("16:9", "9:16"),
        help="Project delivery frame",
    )
    create.add_argument(
        "--slug",
        default=None,
        help="Optional lowercase path slug; derived from title when omitted",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "create":
            result = create_project(
                PROJECT_ROOT,
                title=args.title,
                aspect_ratio=args.aspect_ratio,
                slug=args.slug,
            )
        else:  # pragma: no cover - argparse restricts commands
            raise ProjectSetupError(f"Unknown command: {args.command}")
    except (OSError, ProjectSetupError) as exc:
        json.dump(
            {"status": "error", "error": str(exc)},
            sys.stderr,
            ensure_ascii=False,
        )
        sys.stderr.write("\n")
        return 1

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
