"""Shared validation for scene attempt reviews and canonical promotion state."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ATTEMPT_DECISIONS = {"accepted", "accepted_with_note", "fix_next_scene", "needs_fix"}
PROMOTABLE_DECISIONS = {"accepted", "accepted_with_note", "fix_next_scene", "best_available"}
MAX_ATTEMPTS = 3


class ReviewContractError(ValueError):
    """Raised when review evidence does not satisfy the promotion contract."""


def resolve_path(project_root: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    return path if path.is_absolute() else project_root / path


def attempt_path(config_path: Path, scene_id: str, attempt: int) -> Path:
    if attempt < 1 or attempt > MAX_ATTEMPTS:
        raise ReviewContractError(f"Attempt must be between 1 and {MAX_ATTEMPTS}")
    return config_path.parent / "temp" / "partial" / f"{scene_id}-attempt-{attempt}.mp4"


def contact_sheet_path(config_path: Path, scene_id: str, attempt: int) -> Path:
    return config_path.parent / "temp" / "contact_sheets" / f"{scene_id}-attempt-{attempt}.png"


def review_path(config_path: Path, scene_id: str) -> Path:
    return config_path.parent / "reviews" / f"{scene_id}.json"


def load_review(config_path: Path, scene_id: str) -> dict[str, Any]:
    path = review_path(config_path, scene_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReviewContractError(f"Missing review for scene {scene_id}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewContractError(f"Invalid review JSON for scene {scene_id}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReviewContractError(f"Review for scene {scene_id} must be a JSON object")
    return data


def validate_review(
    config_path: Path,
    scene_id: str,
    project_root: Path,
) -> tuple[dict[str, Any], Path]:
    review = load_review(config_path, scene_id)
    if review.get("scene_id") != scene_id:
        raise ReviewContractError(f"Review scene_id does not match {scene_id}")
    if review.get("execution_mode") not in {"interactive", "autonomous"}:
        raise ReviewContractError(f"Review for {scene_id} has no valid execution_mode")

    decision = review.get("decision")
    if decision not in PROMOTABLE_DECISIONS:
        raise ReviewContractError(
            f"Scene {scene_id} is not promotable: review decision={decision!r}"
        )
    selected_attempt = review.get("selected_attempt")
    if not isinstance(selected_attempt, int) or not 1 <= selected_attempt <= MAX_ATTEMPTS:
        raise ReviewContractError(f"Review for {scene_id} has no valid selected_attempt")

    attempts = review.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ReviewContractError(f"Review for {scene_id} must contain attempts")
    attempt_numbers = [
        item.get("attempt") if isinstance(item, dict) else None for item in attempts
    ]
    if attempt_numbers != list(range(1, len(attempts) + 1)):
        raise ReviewContractError(
            f"Review for {scene_id} attempts must be unique and sequential from 1"
        )
    if len(attempts) > MAX_ATTEMPTS:
        raise ReviewContractError(f"Review for {scene_id} exceeds {MAX_ATTEMPTS} attempts")

    for item in attempts:
        number = item["attempt"]
        if item.get("decision") not in ATTEMPT_DECISIONS:
            raise ReviewContractError(
                f"Review for {scene_id} attempt {number} has an invalid decision"
            )
        if not isinstance(item.get("media_valid"), bool):
            raise ReviewContractError(
                f"Review for {scene_id} attempt {number} has no media_valid boolean"
            )
        if not isinstance(item.get("findings"), list) or not item["findings"]:
            raise ReviewContractError(
                f"Review for {scene_id} attempt {number} has no findings"
            )

        expected_candidate = attempt_path(config_path, scene_id, number).resolve()
        configured_candidate = item.get("candidate_path")
        if not isinstance(configured_candidate, str) or (
            resolve_path(project_root, configured_candidate).resolve() != expected_candidate
        ):
            raise ReviewContractError(
                f"Review for {scene_id} attempt {number} has a mismatched candidate_path"
            )
        if item["media_valid"] and not expected_candidate.is_file():
            raise ReviewContractError(
                f"Media-valid candidate for {scene_id} attempt {number} does not exist"
            )

        expected_sheet = contact_sheet_path(config_path, scene_id, number).resolve()
        configured_sheet = item.get("contact_sheet_path")
        if item["media_valid"] and (
            not isinstance(configured_sheet, str)
            or resolve_path(project_root, configured_sheet).resolve() != expected_sheet
            or not expected_sheet.is_file()
        ):
            raise ReviewContractError(
                f"Review evidence for {scene_id} attempt {number} has no valid contact sheet"
            )

    selected = attempts[selected_attempt - 1]
    if selected.get("media_valid") is not True:
        raise ReviewContractError(
            f"Selected attempt {selected_attempt} for {scene_id} is not media-valid"
        )
    if decision != "best_available" and selected.get("decision") != decision:
        raise ReviewContractError(
            f"Selected attempt decision does not match review decision for {scene_id}"
        )
    if decision == "best_available":
        if review.get("execution_mode") != "autonomous":
            raise ReviewContractError(
                f"Review for {scene_id} may use best_available only in autonomous mode"
            )
        if len(attempts) != MAX_ATTEMPTS or any(
            item.get("decision") != "needs_fix" for item in attempts
        ):
            raise ReviewContractError(
                f"Review for {scene_id} may use best_available only after three failures"
            )
        selection_reason = review.get("selection_reason")
        if not isinstance(selection_reason, str) or not selection_reason.strip():
            raise ReviewContractError(
                f"Review for {scene_id} has no best-available selection_reason"
            )
        unresolved = review.get("unresolved_findings")
        if not isinstance(unresolved, list) or not unresolved:
            raise ReviewContractError(
                f"Review for {scene_id} has no unresolved_findings"
            )
    return review, attempt_path(config_path, scene_id, selected_attempt)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_canonical_binding(
    review: dict[str, Any],
    canonical: Path,
    project_root: Path,
) -> None:
    configured = review.get("canonical_path")
    if not isinstance(configured, str) or (
        resolve_path(project_root, configured).resolve() != canonical.resolve()
    ):
        raise ReviewContractError("Review canonical_path does not match scene output_path")
    expected_hash = review.get("canonical_sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ReviewContractError("Review has no valid canonical_sha256")
    if not canonical.is_file() or sha256_file(canonical) != expected_hash:
        raise ReviewContractError("Canonical video does not match the promoted attempt")


def project_relative(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path.resolve())


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
