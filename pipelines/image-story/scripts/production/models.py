from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


AssetKind = Literal["primary_image", "continuation_image", "video"]


@dataclass(frozen=True)
class AssetNode:
    asset_id: str
    scene_id: str
    kind: AssetKind
    prompt: str
    output_rel: str
    dependencies: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    location_id: str | None = None
    continuation_index: int | None = None
    start_asset_id: str | None = None
    end_asset_id: str | None = None
    provider_hint: str | None = None
    model_hint: str | None = None
    duration: int | None = None
    source: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @property
    def output_path(self) -> Path:
        return Path(self.output_rel)


@dataclass(frozen=True)
class ReferenceInput:
    asset_id: str
    path: Path
    role: str
    sha256: str


@dataclass(frozen=True)
class ProductionPlan:
    project_dir: Path
    nodes: tuple[AssetNode, ...]
    scene_order: tuple[str, ...]
    terminal_image_by_scene: dict[str, str]
    video_candidates: tuple[str, ...]
    missing_video_prompts: tuple[str, ...]
    visual_style_id: str
    visual_style_prompt: str
    aspect_ratio: str
    subject_reference_paths: dict[str, str] = field(default_factory=dict)
    required_subject_anchors: tuple[str, ...] = ()
    required_location_anchors: tuple[str, ...] = ()
    first_subject_asset: dict[str, str] = field(default_factory=dict)
    first_location_asset: dict[str, str] = field(default_factory=dict)

    @property
    def node_by_id(self) -> dict[str, AssetNode]:
        return {node.asset_id: node for node in self.nodes}

    def image_nodes(self) -> tuple[AssetNode, ...]:
        return tuple(node for node in self.nodes if node.kind != "video")

    def video_nodes(self) -> tuple[AssetNode, ...]:
        return tuple(node for node in self.nodes if node.kind == "video")

