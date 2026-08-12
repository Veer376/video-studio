from __future__ import annotations

from pathlib import Path


ROOT_ASSET_PREFIX = "root:"


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_project_dir(project_dir: str | Path) -> Path:
    path = Path(project_dir)
    if not path.is_absolute():
        path = project_root() / path
    return path.resolve()


def is_root_asset_locator(locator: str) -> bool:
    return locator.startswith(ROOT_ASSET_PREFIX)


def resolve_asset_locator(project_dir: Path, locator: str) -> Path:
    """Resolve a project-relative asset or a portable root: asset locator."""
    if not isinstance(locator, str) or not locator.strip():
        raise ValueError("asset locator must be a non-empty string")
    locator = locator.strip()
    if is_root_asset_locator(locator):
        relative = locator[len(ROOT_ASSET_PREFIX):]
        repository_root = project_root().resolve()
        shared_root = (repository_root / "assets").resolve()
        candidate = (repository_root / relative).resolve()
        if not relative or not candidate.is_relative_to(shared_root):
            raise ValueError(
                f"root asset locator must stay under root:assets/: {locator!r}"
            )
        return candidate

    project_root_path = project_dir.resolve()
    candidate = (project_root_path / locator).resolve()
    if not candidate.is_relative_to(project_root_path):
        raise ValueError(f"asset locator must stay inside the project: {locator!r}")
    return candidate


def src_dir() -> Path:
    return project_root() / "src"


def script_path(name: str) -> Path:
    domain_path = src_dir() / "studio" / name
    if domain_path.exists():
        return domain_path
    return src_dir() / "studio" / "scripts" / name
