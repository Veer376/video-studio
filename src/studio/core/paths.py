from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_project_dir(project_dir: str | Path) -> Path:
    path = Path(project_dir)
    if not path.is_absolute():
        path = project_root() / path
    return path.resolve()


def src_dir() -> Path:
    return project_root() / "src"


def script_path(name: str) -> Path:
    domain_path = src_dir() / "studio" / name
    if domain_path.exists():
        return domain_path
    return src_dir() / "studio" / "scripts" / name

