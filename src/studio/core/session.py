from __future__ import annotations

from pathlib import Path

from studio.core.io import read_json, write_json


def load_session(project_dir: Path) -> dict:
    session_path = project_dir / "session.json"
    if not session_path.exists():
        raise FileNotFoundError(f"session.json not found: {session_path}")
    return read_json(session_path)


def save_session(project_dir: Path, session: dict) -> None:
    write_json(project_dir / "session.json", session)


def update_status(project_dir: Path, status: str) -> None:
    session = load_session(project_dir)
    session.setdefault("session", {})["status"] = status
    save_session(project_dir, session)

