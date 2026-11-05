from __future__ import annotations

from pathlib import Path
from typing import Any

from .design import assemble_styled_prompt, load_visual_design
from .io_utils import read_json
from .models import AssetNode, ProductionPlan


class PlanError(ValueError):
    pass


def primary_asset_id(scene_id: str) -> str:
    return f"{scene_id}:primary"


def continuation_asset_id(scene_id: str, index: int) -> str:
    return f"{scene_id}:c{index:02d}"


def video_asset_id(scene_id: str) -> str:
    return f"{scene_id}:video"


def image_output_rel(scene_id: str, continuation_index: int | None = None) -> str:
    if continuation_index is None:
        return f"images/{scene_id}.png"
    return f"images/{scene_id}-c{continuation_index:02d}.png"


def video_output_rel(scene_id: str) -> str:
    return f"videos/{scene_id}.mp4"


def flow_duration_for_scene(duration_seconds: float) -> int:
    for supported in (4, 6, 8, 10):
        if duration_seconds <= supported:
            return supported
    raise PlanError(
        f"Scene duration {duration_seconds:.2f}s exceeds the supported single-clip Flow maximum of 10s"
    )


def load_project_sources(project_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    scenes_path = project_dir / "scenes.json"
    continuity_path = project_dir / "continuity.json"
    if not scenes_path.is_file():
        raise PlanError(f"Missing scenes.json: {scenes_path}")
    if not continuity_path.is_file():
        raise PlanError(f"Missing continuity.json: {continuity_path}")
    return read_json(scenes_path), read_json(continuity_path)


def _load_video_prompts(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    if not path.is_file():
        raise PlanError(f"Video prompt map does not exist: {path}")
    data = read_json(path)
    raw = data.get("scenes", {})
    if not isinstance(raw, dict):
        raise PlanError(f"{path}: scenes must be an object keyed by scene id")
    result: dict[str, dict[str, Any]] = {}
    for scene_id, value in raw.items():
        if isinstance(value, str):
            result[str(scene_id)] = {"prompt": value}
        elif isinstance(value, dict):
            result[str(scene_id)] = dict(value)
        else:
            raise PlanError(f"{path}: video prompt for {scene_id} must be a string or object")
    return result


def _validate_sources(scenes_data: dict[str, Any], continuity_data: dict[str, Any]) -> list[dict[str, Any]]:
    scenes = scenes_data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise PlanError("scenes.json must contain a non-empty scenes array")
    subjects = continuity_data.get("subjects")
    locations = continuity_data.get("locations")
    if not isinstance(subjects, dict):
        raise PlanError("continuity.json subjects must be an object")
    if not isinstance(locations, dict):
        raise PlanError("continuity.json locations must be an object")

    seen: dict[str, int] = {}
    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise PlanError(f"scene at index {index} is not an object")
        scene_id = scene.get("id")
        if not isinstance(scene_id, str) or not scene_id:
            raise PlanError(f"scene at index {index} has no valid id")
        if scene_id in seen:
            raise PlanError(f"duplicate scene id: {scene_id}")
        seen[scene_id] = index
        prompt = scene.get("image_prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise PlanError(f"{scene_id}.image_prompt is missing")
        continuation_prompts = scene.get("continuation_image_prompts") or []
        if not isinstance(continuation_prompts, list):
            raise PlanError(f"{scene_id}.continuation_image_prompts must be a list")
        for prompt_index, continuation_prompt in enumerate(continuation_prompts, 1):
            if not isinstance(continuation_prompt, str) or not continuation_prompt.strip():
                raise PlanError(f"{scene_id}.continuation_image_prompts[{prompt_index - 1}] is empty")
        for subject in scene.get("subjects") or []:
            if subject not in subjects:
                raise PlanError(f"{scene_id} uses undefined continuity subject {subject!r}")
        location_id = scene.get("location_id")
        if location_id is not None and location_id not in locations:
            raise PlanError(f"{scene_id} uses undefined continuity location {location_id!r}")
        reference_scene_id = scene.get("reference_scene_id")
        if reference_scene_id is not None:
            if reference_scene_id not in seen:
                if reference_scene_id not in {s.get("id") for s in scenes}:
                    raise PlanError(f"{scene_id} references missing scene {reference_scene_id}")
                raise PlanError(f"{scene_id} references a non-earlier scene {reference_scene_id}")
            if seen[reference_scene_id] >= index:
                raise PlanError(f"{scene_id} references a non-earlier scene {reference_scene_id}")
    return scenes


def _resolve_local_asset_selector(scene_id: str, selector: str, terminal: str) -> str:
    selector = selector.strip()
    if selector == "primary":
        return primary_asset_id(scene_id)
    if selector == "terminal":
        return terminal
    if selector.startswith("c") and selector[1:].isdigit():
        return continuation_asset_id(scene_id, int(selector[1:]))
    if ":" in selector:
        return selector
    raise PlanError(f"Unsupported asset selector for {scene_id}: {selector!r}")


def build_plan(
    project_dir: Path,
    *,
    video_prompts_path: Path | None = None,
) -> ProductionPlan:
    project_dir = project_dir.resolve()
    scenes_data, continuity_data = load_project_sources(project_dir)
    design = load_visual_design(project_dir)
    scenes = _validate_sources(scenes_data, continuity_data)
    video_prompts = _load_video_prompts(video_prompts_path)

    subject_reference_paths = {
        key: str(value.get("image_path")).strip()
        for key, value in continuity_data.get("subjects", {}).items()
        if isinstance(value, dict)
        and isinstance(value.get("image_path"), str)
        and str(value.get("image_path")).strip()
    }

    required_subject_anchors = tuple(
        key
        for key, value in continuity_data.get("subjects", {}).items()
        if isinstance(value, dict)
        and key not in subject_reference_paths
        and (
            "lock" in str(value.get("appearance_status") or "").lower()
            or value.get("canonical_reference") is not None
        )
    )
    required_location_anchors = tuple(
        key
        for key, value in continuity_data.get("locations", {}).items()
        if isinstance(value, dict)
        and (
            "lock" in str(value.get("visual_status") or "").lower()
            or value.get("canonical_reference") is not None
        )
    )

    nodes: list[AssetNode] = []
    terminal_by_scene: dict[str, str] = {}
    first_subject_asset: dict[str, str] = {}
    first_location_asset: dict[str, str] = {}
    scene_ids = {str(scene["id"]) for scene in scenes}
    unknown_video_scenes = sorted(set(video_prompts) - scene_ids)
    if unknown_video_scenes:
        raise PlanError(f"video-prompts references unknown scenes: {', '.join(unknown_video_scenes)}")

    video_candidates: list[str] = []
    missing_video_prompts: list[str] = []

    for scene in scenes:
        scene_id = str(scene["id"])
        subjects = tuple(str(value) for value in (scene.get("subjects") or []))
        location_id = scene.get("location_id")
        reference_scene_id = scene.get("reference_scene_id")
        primary_dependencies: tuple[str, ...] = ()
        if reference_scene_id:
            primary_dependencies = (terminal_by_scene[str(reference_scene_id)],)

        primary_id = primary_asset_id(scene_id)
        for subject in subjects:
            first_subject_asset.setdefault(subject, primary_id)
        if location_id is not None:
            first_location_asset.setdefault(str(location_id), primary_id)
        nodes.append(
            AssetNode(
                asset_id=primary_id,
                scene_id=scene_id,
                kind="primary_image",
                prompt=assemble_styled_prompt(
                    str(scene["image_prompt"]),
                    label=f"{scene_id}.image_prompt",
                    design=design,
                ),
                output_rel=image_output_rel(scene_id),
                dependencies=primary_dependencies,
                subjects=subjects,
                location_id=str(location_id) if location_id is not None else None,
                source=scene,
            )
        )

        previous_id = primary_id
        for continuation_index, continuation_prompt in enumerate(
            scene.get("continuation_image_prompts") or [], 1
        ):
            current_id = continuation_asset_id(scene_id, continuation_index)
            nodes.append(
                AssetNode(
                    asset_id=current_id,
                    scene_id=scene_id,
                    kind="continuation_image",
                    prompt=assemble_styled_prompt(
                        str(continuation_prompt),
                        label=f"{scene_id}.continuation_image_prompts[{continuation_index - 1}]",
                        design=design,
                    ),
                    output_rel=image_output_rel(scene_id, continuation_index),
                    dependencies=(previous_id,),
                    subjects=subjects,
                    location_id=str(location_id) if location_id is not None else None,
                    continuation_index=continuation_index,
                    source=scene,
                )
            )
            previous_id = current_id
        terminal_by_scene[scene_id] = previous_id

        strategy = str(scene.get("asset_strategy") or "")
        if "video" in strategy.lower():
            video_candidates.append(scene_id)
            if scene_id not in video_prompts:
                missing_video_prompts.append(scene_id)

        video_spec = video_prompts.get(scene_id)
        if video_spec is None:
            continue
        raw_prompt = video_spec.get("prompt")
        if not isinstance(raw_prompt, str) or not raw_prompt.strip():
            raise PlanError(f"video prompt for {scene_id} is empty")
        start_asset = _resolve_local_asset_selector(
            scene_id,
            str(video_spec.get("start_asset") or "primary"),
            terminal_by_scene[scene_id],
        )
        default_end = "terminal" if terminal_by_scene[scene_id] != primary_id else "primary"
        end_asset = _resolve_local_asset_selector(
            scene_id,
            str(video_spec.get("end_asset") or default_end),
            terminal_by_scene[scene_id],
        )
        dependencies = tuple(dict.fromkeys((start_asset, end_asset)))
        provider = str(video_spec.get("provider") or "flow")
        duration_value = video_spec.get("duration")
        if duration_value is None:
            duration_value = flow_duration_for_scene(float(scene.get("duration") or 0))
        duration = int(duration_value)
        if duration <= 0:
            raise PlanError(f"video duration for {scene_id} must be positive")
        nodes.append(
            AssetNode(
                asset_id=video_asset_id(scene_id),
                scene_id=scene_id,
                kind="video",
                prompt=assemble_styled_prompt(
                    raw_prompt,
                    label=f"video prompt for {scene_id}",
                    design=design,
                ),
                output_rel=video_output_rel(scene_id),
                dependencies=dependencies,
                subjects=subjects,
                location_id=str(location_id) if location_id is not None else None,
                start_asset_id=start_asset,
                end_asset_id=end_asset,
                provider_hint=provider,
                model_hint=(str(video_spec["model"]) if video_spec.get("model") else None),
                duration=duration,
                source=scene,
            )
        )

    node_ids = {node.asset_id for node in nodes}
    for node in nodes:
        missing = [dep for dep in node.dependencies if dep not in node_ids]
        if missing:
            raise PlanError(f"{node.asset_id} depends on unknown assets: {', '.join(missing)}")

    return ProductionPlan(
        project_dir=project_dir,
        nodes=tuple(nodes),
        scene_order=tuple(str(scene["id"]) for scene in scenes),
        terminal_image_by_scene=terminal_by_scene,
        video_candidates=tuple(video_candidates),
        missing_video_prompts=tuple(missing_video_prompts),
        visual_style_id=design.style_id,
        visual_style_prompt=design.style_prompt,
        aspect_ratio=design.aspect_ratio,
        subject_reference_paths=subject_reference_paths,
        required_subject_anchors=required_subject_anchors,
        required_location_anchors=required_location_anchors,
        first_subject_asset=first_subject_asset,
        first_location_asset=first_location_asset,
    )

