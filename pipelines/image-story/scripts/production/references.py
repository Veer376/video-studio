from __future__ import annotations

from pathlib import Path

from .anchors import AnchorBinding, AnchorRegistry
from .io_utils import sha256_file
from .manifest import ManifestStore
from .models import AssetNode, ProductionPlan, ReferenceInput
from .verify import verify_image


class ReferenceError(RuntimeError):
    pass


def _dependency_carries_subject(node: AssetNode, subject_id: str, plan: ProductionPlan) -> bool:
    for dependency_id in node.dependencies:
        dependency = plan.node_by_id.get(dependency_id)
        if dependency is not None and subject_id in dependency.subjects:
            return True
    return False


def _dependency_carries_location(node: AssetNode, location_id: str, plan: ProductionPlan) -> bool:
    for dependency_id in node.dependencies:
        dependency = plan.node_by_id.get(dependency_id)
        if dependency is not None and dependency.location_id == location_id:
            return True
    return False


def _completed_asset_reference(
    *,
    asset_id: str,
    role: str,
    plan: ProductionPlan,
    manifest: ManifestStore,
) -> ReferenceInput:
    node = plan.node_by_id.get(asset_id)
    if node is None:
        raise ReferenceError(f"Anchor/dependency references unknown asset {asset_id}")
    if node.kind == "video":
        raise ReferenceError(f"Image reference cannot point to video asset {asset_id}")
    record = manifest.get(asset_id)
    if not record or record.get("status") != "complete":
        raise ReferenceError(f"Required reference asset is not complete: {asset_id}")
    path = plan.project_dir / node.output_rel
    verify_image(path)
    actual_sha = sha256_file(path)
    recorded_sha = record.get("output_sha256")
    if not isinstance(recorded_sha, str) or not recorded_sha:
        raise ReferenceError(f"Reference asset has no recorded output hash: {asset_id}")
    if recorded_sha != actual_sha:
        raise ReferenceError(
            f"Reference asset changed after manifest verification: {asset_id}"
        )
    return ReferenceInput(asset_id=asset_id, path=path, role=role, sha256=actual_sha)


def _optional_subject_reference(
    *,
    subject_id: str,
    relative_path: str,
    plan: ProductionPlan,
) -> ReferenceInput | None:
    """Resolve a canonical subject sheet when it is physically available.

    Subject sheets are optional identity references, not generated DAG assets.
    Missing files are intentionally skipped so scene generation can continue.
    Existing files must still be valid images and remain inside the project.
    """

    project_root = plan.project_dir.resolve()
    path = (project_root / relative_path).resolve()
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise ReferenceError(
            f"Subject reference for {subject_id} escapes project directory: {relative_path}"
        ) from exc
    if not path.is_file():
        return None
    verify_image(path)
    return ReferenceInput(
        asset_id=f"subject:{subject_id}",
        path=path,
        role=(
            f"canonical identity sheet for subject {subject_id}; preserve identity/body proportions only, "
            "while scene continuity controls pose, wardrobe, composition, action, and environment"
        ),
        sha256=sha256_file(path),
    )


def image_references_for_node(
    node: AssetNode,
    *,
    plan: ProductionPlan,
    manifest: ManifestStore,
    anchors: AnchorRegistry,
    max_references: int = 4,
) -> tuple[ReferenceInput, ...]:
    if node.kind == "video":
        raise ReferenceError("image_references_for_node cannot be used for a video node")

    requested: list[tuple[str, str, AnchorBinding | None, ReferenceInput | None]] = []
    if node.dependencies:
        if len(node.dependencies) != 1:
            raise ReferenceError(
                f"Image asset {node.asset_id} unexpectedly has {len(node.dependencies)} dependencies"
            )
        requested.append(
            (node.dependencies[0], "previous generated visual state for continuity", None, None)
        )

    for subject_id in node.subjects:
        subject_path = plan.subject_reference_paths.get(subject_id)
        if subject_path:
            direct_reference = _optional_subject_reference(
                subject_id=subject_id,
                relative_path=subject_path,
                plan=plan,
            )
            if direct_reference is not None:
                requested.append(
                    (
                        direct_reference.asset_id,
                        direct_reference.role,
                        None,
                        direct_reference,
                    )
                )
                continue
        binding = anchors.get_subject(subject_id)
        if binding:
            requested.append(
                (
                    binding.asset_id,
                    f"approved continuity anchor for subject {subject_id}",
                    binding,
                    None,
                )
            )
        elif (
            subject_id in plan.required_subject_anchors
            and plan.first_subject_asset.get(subject_id) != node.asset_id
            and not _dependency_carries_subject(node, subject_id, plan)
        ):
            candidate = plan.first_subject_asset.get(subject_id)
            raise ReferenceError(
                f"{node.asset_id} needs an approved anchor for recurring subject {subject_id}. "
                f"Review an established image (first candidate: {candidate}) and approve it with the anchor command."
            )
    if node.location_id:
        binding = anchors.get_location(node.location_id)
        if binding:
            requested.append(
                (
                    binding.asset_id,
                    f"approved continuity anchor for location {node.location_id}",
                    binding,
                    None,
                )
            )
        elif (
            node.location_id in plan.required_location_anchors
            and plan.first_location_asset.get(node.location_id) != node.asset_id
            and not _dependency_carries_location(node, node.location_id, plan)
        ):
            candidate = plan.first_location_asset.get(node.location_id)
            raise ReferenceError(
                f"{node.asset_id} needs an approved anchor for recurring location {node.location_id}. "
                f"Review an established image (first candidate: {candidate}) and approve it with the anchor command."
            )

    deduped: list[
        tuple[str, list[str], list[AnchorBinding], ReferenceInput | None]
    ] = []
    positions: dict[str, int] = {}
    for asset_id, role, binding, direct_reference in requested:
        if asset_id == node.asset_id:
            if binding is not None:
                # An approved anchor may point to the asset currently being regenerated.
                # It cannot be used as its own input; later scenes will force reapproval
                # if the bytes/fingerprint change.
                continue
            raise ReferenceError(f"Asset {node.asset_id} cannot reference itself")
        if asset_id in positions:
            deduped[positions[asset_id]][1].append(role)
            if binding is not None:
                deduped[positions[asset_id]][2].append(binding)
        else:
            positions[asset_id] = len(deduped)
            deduped.append(
                (
                    asset_id,
                    [role],
                    [binding] if binding is not None else [],
                    direct_reference,
                )
            )

    if len(deduped) > max_references:
        overflow = ", ".join(
            asset_id for asset_id, _, _, _ in deduped[max_references:]
        )
        raise ReferenceError(
            f"{node.asset_id} needs {len(deduped)} references but provider budget is "
            f"{max_references}; refusing to silently drop: {overflow}"
        )

    references: list[ReferenceInput] = []
    for asset_id, roles, bindings, direct_reference in deduped:
        if direct_reference is not None:
            reference = ReferenceInput(
                asset_id=direct_reference.asset_id,
                path=direct_reference.path,
                role="; ".join(roles),
                sha256=direct_reference.sha256,
            )
        else:
            reference = _completed_asset_reference(
                asset_id=asset_id,
                role="; ".join(roles),
                plan=plan,
                manifest=manifest,
            )
        record = manifest.get(asset_id) or {}
        for binding in bindings:
            if (
                binding.output_sha256 != reference.sha256
                or binding.fingerprint != record.get("fingerprint")
            ):
                raise ReferenceError(
                    f"Approved anchor {asset_id} changed after approval; reapprove exact bytes before use"
                )
        references.append(reference)
    return tuple(references)


def video_frame_paths(
    node: AssetNode,
    *,
    plan: ProductionPlan,
    manifest: ManifestStore,
) -> tuple[ReferenceInput, ReferenceInput]:
    if node.kind != "video" or not node.start_asset_id or not node.end_asset_id:
        raise ReferenceError(f"Video node lacks start/end assets: {node.asset_id}")
    start = _completed_asset_reference(
        asset_id=node.start_asset_id,
        role="exact video start frame",
        plan=plan,
        manifest=manifest,
    )
    end = _completed_asset_reference(
        asset_id=node.end_asset_id,
        role="intended video end frame",
        plan=plan,
        manifest=manifest,
    )
    return start, end

