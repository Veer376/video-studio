from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import read_json


SUPPORTED_ASPECT_RATIOS = {"16:9", "9:16"}

# These are rendering-medium declarations, not ordinary scene content.  The
# project-level visual design owns the medium; scene prompts own subject,
# action, setting, lighting, framing, and continuity.
CONFLICTING_MEDIUM_PHRASES = (
    "oil painting",
    "anime",
    "clay stop-motion",
    "clay stop motion",
    "3d cartoon",
    "stylized 3d cartoon",
    "photorealistic",
    "photographic finish",
    "watercolor painting",
    "watercolour painting",
)


@dataclass(frozen=True)
class VisualDesign:
    style_id: str
    style_prompt: str
    aspect_ratio: str


def load_visual_design(project_dir: Path) -> VisualDesign:
    """Load the approved project-level rendering design from session.json.

    Production intentionally fails closed when the lock is absent.  A scene
    plan without its approved rendering medium is incomplete input, not a
    reason to silently fall back to a provider default.
    """

    session_path = project_dir / "session.json"
    if not session_path.is_file():
        raise ValueError(
            f"approved visual design is missing: {session_path}; "
            "persist session.visual before production"
        )

    session = read_json(session_path)
    visual = session.get("visual")
    if not isinstance(visual, dict):
        raise ValueError("session.visual must be an object")

    style_id = visual.get("style_id")
    style_prompt = visual.get("style_prompt")
    aspect_ratio = visual.get("aspect_ratio")

    if not isinstance(style_id, str) or not style_id.strip():
        raise ValueError("session.visual.style_id must be a non-empty string")
    if not isinstance(style_prompt, str) or not style_prompt.strip():
        raise ValueError("session.visual.style_prompt must be a non-empty string")
    if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
        raise ValueError(
            "session.visual.aspect_ratio must be one of: "
            + ", ".join(sorted(SUPPORTED_ASPECT_RATIOS))
        )

    return VisualDesign(
        style_id=style_id.strip(),
        style_prompt=style_prompt.strip(),
        aspect_ratio=str(aspect_ratio),
    )


def strip_duplicated_style(prompt: str, style_prompt: str) -> str:
    """Remove an already-copied style prefix so production adds it once."""

    normalized = prompt.strip()
    style = style_prompt.strip()
    for separator in (" — ", ", ", " - ", ": "):
        prefix = f"{style}{separator}"
        if normalized.startswith(prefix):
            return normalized[len(prefix) :].strip()
    return normalized


def assert_style_neutral_prompt(prompt: str, *, label: str, design: VisualDesign) -> None:
    """Reject scene-local attempts to switch the global rendering medium."""

    lowered = prompt.casefold()
    design_text = f"{design.style_id} {design.style_prompt}".casefold()
    conflicts = [
        phrase
        for phrase in CONFLICTING_MEDIUM_PHRASES
        if phrase in lowered and phrase not in design_text
    ]
    if conflicts:
        raise ValueError(
            f"{label} declares a rendering medium controlled by session.visual: "
            + ", ".join(sorted(set(conflicts)))
        )


def assemble_styled_prompt(prompt: str, *, label: str, design: VisualDesign) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError(f"{label} is empty")
    raw = strip_duplicated_style(prompt, design.style_prompt)
    assert_style_neutral_prompt(raw, label=label, design=design)
    if not raw:
        return design.style_prompt
    return f"{design.style_prompt} — {raw}"

