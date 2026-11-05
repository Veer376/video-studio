#!/usr/bin/env python3
"""Validate active scene reviews and legacy canonical review records."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


PROMOTABLE_DECISIONS = {"accepted", "accepted_with_note", "fix_next_scene"}
MAX_GENERATIONS = 2


class ReviewContractError(ValueError):
    """Raised when review evidence does not match the reviewed video."""


def resolve_path(project_root: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    return path if path.is_absolute() else project_root / path


def project_relative(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path.resolve())


def review_path(config_path: Path, scene_id: str) -> Path:
    return config_path.parent / "reviews" / f"{scene_id}.json"


def active_contact_sheet_path(config_path: Path, scene_id: str) -> Path:
    return config_path.parent / "temp" / "contact_sheets" / f"{scene_id}.png"


def archived_path(path: Path, number: int) -> Path:
    if number < 1 or number > MAX_GENERATIONS:
        raise ReviewContractError(
            f"Archive number must be between 1 and {MAX_GENERATIONS}"
        )
    return path.with_name(f"{path.stem}-a{number}{path.suffix}")


def load_review(config_path: Path, scene_id: str) -> dict[str, Any]:
    path = review_path(config_path, scene_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReviewContractError(f"Missing review for scene {scene_id}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewContractError(
            f"Invalid review JSON for scene {scene_id}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ReviewContractError(f"Review for scene {scene_id} must be a JSON object")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scene_output_path(
    config_path: Path,
    scene_id: str,
    project_root: Path,
) -> Path:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewContractError(f"Cannot read {config_path}: {exc}") from exc
    scenes = config.get("scenes") if isinstance(config, dict) else None
    if not isinstance(scenes, list):
        raise ReviewContractError(f"{config_path} has no scenes array")
    for scene in scenes:
        if isinstance(scene, dict) and scene.get("id") == scene_id:
            output = scene.get("output_path")
            if not isinstance(output, str) or not output:
                break
            return resolve_path(project_root, output).resolve()
    raise ReviewContractError(f"Scene {scene_id} has no output_path in {config_path}")


def _validate_active_review(
    config_path: Path,
    scene_id: str,
    project_root: Path,
    review: dict[str, Any],
) -> Path:
    decision = review.get("decision")
    if decision not in PROMOTABLE_DECISIONS:
        raise ReviewContractError(
            f"Scene {scene_id} is not accepted: review decision={decision!r}"
        )
    active = scene_output_path(config_path, scene_id, project_root)
    configured = review.get("video_path")
    if not isinstance(configured, str) or (
        resolve_path(project_root, configured).resolve() != active
    ):
        raise ReviewContractError(f"Review for {scene_id} does not target its active video")
    if review.get("media_valid") is not True:
        raise ReviewContractError(f"Active video for {scene_id} is not media-valid")
    if not active.is_file():
        raise ReviewContractError(f"Active video for {scene_id} does not exist: {active}")
    expected_hash = review.get("video_sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ReviewContractError(f"Review for {scene_id} has no video_sha256")
    if sha256_file(active) != expected_hash:
        raise ReviewContractError(f"Active video for {scene_id} changed after generation")
    findings = review.get("findings")
    if not isinstance(findings, list):
        raise ReviewContractError(f"Review for {scene_id} findings must be a list")
    sheet_value = review.get("contact_sheet_path")
    expected_sheet = active_contact_sheet_path(config_path, scene_id).resolve()
    if not isinstance(sheet_value, str) or (
        resolve_path(project_root, sheet_value).resolve() != expected_sheet
        or not expected_sheet.is_file()
    ):
        raise ReviewContractError(f"Review for {scene_id} has no valid contact sheet")
    history = review.get("history", [])
    if not isinstance(history, list):
        raise ReviewContractError(f"Review for {scene_id} history must be a list")
    return active


def _legacy_attempt_path(config_path: Path, scene_id: str, attempt: int) -> Path:
    if attempt < 1:
        raise ReviewContractError("Legacy attempt number must be positive")
    return config_path.parent / "temp" / "partial" / f"{scene_id}-attempt-{attempt}.mp4"


def _validate_legacy_review(
    config_path: Path,
    scene_id: str,
    project_root: Path,
    review: dict[str, Any],
) -> Path:
    """Keep existing rendered stories valid while new work uses active videos."""
    decision = review.get("decision")
    if decision not in PROMOTABLE_DECISIONS and decision != "best_available":
        raise ReviewContractError(
            f"Scene {scene_id} is not accepted: review decision={decision!r}"
        )
    selected = review.get("selected_attempt")
    attempts = review.get("attempts")
    if not isinstance(selected, int) or selected < 1:
        raise ReviewContractError(f"Legacy review for {scene_id} has no selected attempt")
    if not isinstance(attempts, list) or selected > len(attempts):
        raise ReviewContractError(f"Legacy review for {scene_id} has invalid history")
    item = attempts[selected - 1]
    if not isinstance(item, dict) or item.get("attempt") != selected:
        raise ReviewContractError(f"Legacy review for {scene_id} has mismatched history")
    if item.get("media_valid") is not True:
        raise ReviewContractError(f"Legacy selected video for {scene_id} is invalid")
    if item.get("decision") != decision and decision != "best_available":
        raise ReviewContractError(f"Legacy selected decision for {scene_id} does not match")
    promoted = review.get("promoted_attempt")
    if promoted is not None and promoted != selected:
        raise ReviewContractError(f"Legacy promoted attempt for {scene_id} does not match")
    candidate = _legacy_attempt_path(config_path, scene_id, selected).resolve()
    configured = item.get("candidate_path")
    if not isinstance(configured, str) or (
        resolve_path(project_root, configured).resolve() != candidate
    ):
        raise ReviewContractError(f"Legacy candidate path for {scene_id} does not match")
    if not candidate.is_file():
        raise ReviewContractError(f"Legacy candidate for {scene_id} does not exist")
    sheet_value = item.get("contact_sheet_path")
    if not isinstance(sheet_value, str) or not resolve_path(
        project_root, sheet_value
    ).is_file():
        raise ReviewContractError(f"Legacy contact sheet for {scene_id} does not exist")
    return candidate


def validate_review(
    config_path: Path,
    scene_id: str,
    project_root: Path,
) -> tuple[dict[str, Any], Path]:
    review = load_review(config_path, scene_id)
    if review.get("scene_id") != scene_id:
        raise ReviewContractError(f"Review scene_id does not match {scene_id}")
    if "attempts" in review:
        reviewed = _validate_legacy_review(config_path, scene_id, project_root, review)
    else:
        reviewed = _validate_active_review(config_path, scene_id, project_root, review)
    return review, reviewed


def validate_active_bytes(
    review: dict[str, Any],
    active: Path,
    project_root: Path,
) -> None:
    """Verify the active file before it is archived after review."""
    if "attempts" in review:
        validate_canonical_binding(review, active, project_root)
        return
    configured = review.get("video_path")
    if not isinstance(configured, str) or (
        resolve_path(project_root, configured).resolve() != active.resolve()
    ):
        raise ReviewContractError("Review does not target the active video")
    expected_hash = review.get("video_sha256")
    if not isinstance(expected_hash, str) or sha256_file(active) != expected_hash:
        raise ReviewContractError("Active video does not match its review record")


def begin_active_review(
    config_path: Path,
    scene_id: str,
    active: Path,
    project_root: Path,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    review = {
        "scene_id": scene_id,
        "decision": "pending_review",
        "video_path": project_relative(active, project_root),
        "video_sha256": sha256_file(active),
        "contact_sheet_path": None,
        "media_valid": None,
        "findings": [],
        "diagnosis": None,
        "repair_applied": None,
        "history": list(history or []),
        "next_action": "review",
    }
    write_review_atomic(review_path(config_path, scene_id), review)
    return review


def validate_canonical_binding(
    review: dict[str, Any],
    canonical: Path,
    project_root: Path,
) -> None:
    if "attempts" not in review:
        configured = review.get("video_path")
        expected_hash = review.get("video_sha256")
        if not isinstance(configured, str) or (
            resolve_path(project_root, configured).resolve() != canonical.resolve()
        ):
            raise ReviewContractError("Review does not match the active scene video")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise ReviewContractError("Review has no valid video_sha256")
        if not canonical.is_file() or sha256_file(canonical) != expected_hash:
            raise ReviewContractError("Active scene video does not match its review")
        return

    configured = review.get("canonical_path")
    if not isinstance(configured, str) or (
        resolve_path(project_root, configured).resolve() != canonical.resolve()
    ):
        raise ReviewContractError("Legacy canonical_path does not match output_path")
    expected_hash = review.get("canonical_sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ReviewContractError("Legacy review has no valid canonical_sha256")
    if not canonical.is_file() or sha256_file(canonical) != expected_hash:
        raise ReviewContractError("Legacy canonical video does not match its review")


def write_review_atomic(path: Path, review: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.stem}-",
        suffix=".json.tmp",
        delete=False,
    ) as file:
        json.dump(review, file, ensure_ascii=False, indent=2)
        file.write("\n")
        temporary = Path(file.name)
    os.replace(temporary, path)
