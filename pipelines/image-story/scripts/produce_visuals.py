#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.production.anchors import AnchorRegistry
from scripts.production.io_utils import ProjectLock, load_env_file
from scripts.production.manifest import ManifestStore
from scripts.production.planner import PlanError, build_plan, load_project_sources
from scripts.production.providers import ProviderError
from scripts.production.runner import (
    ProductionError,
    ProductionRunner,
    ProductionSettings,
    select_assets,
)
from scripts.production.verify import verify_image


def project_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"Project directory does not exist: {path}")
    return path


def add_project(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project_dir", type=project_path)
    parser.add_argument(
        "--video-prompts",
        type=Path,
        help="Video prompt map; defaults to <project>/bin/video-prompts.json when present",
    )


def resolve_video_prompts(project_dir: Path, configured: Path | None) -> Path | None:
    if configured is not None:
        return configured.expanduser().resolve()
    default = project_dir / "bin/video-prompts.json"
    return default if default.is_file() else None


def build_project_plan(args: argparse.Namespace):
    return build_plan(
        args.project_dir,
        video_prompts_path=resolve_video_prompts(args.project_dir, args.video_prompts),
    )


def plan_summary(plan) -> dict[str, object]:
    kinds = Counter(node.kind for node in plan.nodes)
    cross_scene_edges = sum(
        1
        for node in plan.nodes
        if node.kind == "primary_image"
        and node.dependencies
        and plan.node_by_id[node.dependencies[0]].scene_id != node.scene_id
    )
    return {
        "project": str(plan.project_dir),
        "visual_style_id": plan.visual_style_id,
        "aspect_ratio": plan.aspect_ratio,
        "scenes": len(plan.scene_order),
        "primary_images": kinds["primary_image"],
        "continuation_images": kinds["continuation_image"],
        "image_assets": kinds["primary_image"] + kinds["continuation_image"],
        "video_candidates": len(plan.video_candidates),
        "video_assets_with_prompts": kinds["video"],
        "missing_video_prompts": list(plan.missing_video_prompts),
        "cross_scene_reference_edges": cross_scene_edges,
        "required_subject_anchors": list(plan.required_subject_anchors),
        "required_location_anchors": list(plan.required_location_anchors),
    }


def cmd_plan(args: argparse.Namespace) -> int:
    plan = build_project_plan(args)
    summary = plan_summary(plan)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    print(f"Project: {summary['project']}")
    print(
        f"Visual design: {summary['visual_style_id']} "
        f"({summary['aspect_ratio']})"
    )
    print(f"Scenes: {summary['scenes']}")
    print(
        f"Images: {summary['image_assets']} "
        f"({summary['primary_images']} primary + {summary['continuation_images']} continuation)"
    )
    print(f"Cross-scene reference edges: {summary['cross_scene_reference_edges']}")
    print(
        f"Videos: {summary['video_assets_with_prompts']} planned from "
        f"{summary['video_candidates']} candidate scene(s)"
    )
    missing = summary["missing_video_prompts"]
    if missing:
        print("Video prompts still required: " + ", ".join(missing))
    if plan.required_subject_anchors or plan.required_location_anchors:
        print(
            "Continuity approval gates: "
            f"{len(plan.required_subject_anchors)} subject anchor(s), "
            f"{len(plan.required_location_anchors)} location anchor(s)"
        )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    plan = build_project_plan(args)
    manifest = ManifestStore(args.project_dir / "production-manifest.json", args.project_dir)
    snapshot = manifest.snapshot()
    records = snapshot.get("assets", {})
    counts = Counter(
        str(record.get("status") or "unknown")
        for record in records.values()
        if isinstance(record, dict)
    )
    print(json.dumps({"plan": plan_summary(plan), "manifest_statuses": counts}, indent=2, ensure_ascii=False, default=dict))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    plan = build_project_plan(args)
    phase = "images" if args.images_only else "videos" if args.videos_only else "all"
    selected = select_assets(
        plan,
        scene_ids=args.scene or (),
        through_scene=args.through,
        phase=phase,
    )
    if phase == "videos" and not plan.video_nodes():
        raise ProductionError(
            "No approved video prompts are available. Create bin/video-prompts.json before running videos."
        )
    if args.dry_run:
        ordered = [node.asset_id for node in plan.nodes if node.asset_id in selected]
        print(f"DRY RUN: {len(ordered)} asset(s), no providers called")
        for asset_id in ordered:
            node = plan.node_by_id[asset_id]
            print(f"  {asset_id:<24} {node.kind:<20} -> {node.output_rel}")
        return 0

    with ProjectLock(args.project_dir / ".production.lock"):
        manifest = ManifestStore(args.project_dir / "production-manifest.json", args.project_dir)
        anchors = AnchorRegistry(args.project_dir / "production-anchors.json")
        requested_aspect = args.aspect_ratio or plan.aspect_ratio
        if requested_aspect != plan.aspect_ratio:
            raise ProductionError(
                f"--aspect-ratio {requested_aspect} conflicts with locked "
                f"session.visual.aspect_ratio {plan.aspect_ratio}"
            )
        settings = ProductionSettings(
            image_provider=args.image_provider,
            image_model=args.image_model,
            video_provider=args.video_provider,
            video_model=args.video_model,
            aspect_ratio=requested_aspect,
            flow_poll_seconds=args.flow_poll_seconds,
            flow_poll_timeout=args.flow_poll_timeout,
        )
        runner = ProductionRunner(
            plan=plan,
            manifest=manifest,
            anchors=anchors,
            settings=settings,
        )
        result = runner.run(selected, phase=phase)
    print(
        f"Complete: {len(result.completed)} generated, {len(result.skipped)} already current, "
        f"{len(result.blocked)} blocked"
    )
    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    plan = build_project_plan(args)
    if args.asset not in plan.node_by_id:
        raise ProductionError(f"Unknown asset: {args.asset}")
    with ProjectLock(args.project_dir / ".production.lock"):
        manifest = ManifestStore(args.project_dir / "production-manifest.json", args.project_dir)
        manifest.reset_for_retry(args.asset)
    print(f"RESET {args.asset}: explicit retry is now permitted")
    return 0


def cmd_anchor(args: argparse.Namespace) -> int:
    plan = build_project_plan(args)
    with ProjectLock(args.project_dir / ".production.lock"):
        manifest = ManifestStore(args.project_dir / "production-manifest.json", args.project_dir)
        node = plan.node_by_id.get(args.asset)
        if node is None or node.kind == "video":
            raise ProductionError(f"Anchor must point to a known image asset: {args.asset}")
        record = manifest.get(args.asset)
        if not record or record.get("status") != "complete":
            raise ProductionError(f"Anchor asset is not complete: {args.asset}")
        verify_image(args.project_dir / node.output_rel)
        output_sha256 = record.get("output_sha256")
        fingerprint = record.get("fingerprint")
        if not isinstance(output_sha256, str) or not isinstance(fingerprint, str):
            raise ProductionError(f"Anchor asset lacks verified hash/fingerprint: {args.asset}")
        scenes_data, continuity_data = load_project_sources(args.project_dir)
        del scenes_data
        registry = AnchorRegistry(args.project_dir / "production-anchors.json")
        if args.subject:
            if args.subject not in continuity_data.get("subjects", {}):
                raise ProductionError(f"Unknown continuity subject: {args.subject}")
            if args.subject not in node.subjects:
                raise ProductionError(
                    f"Cannot approve {args.subject} from {args.asset}: the source scene does not declare that subject"
                )
            registry.set_subject(
                args.subject,
                args.asset,
                output_sha256=output_sha256,
                fingerprint=fingerprint,
            )
            print(f"APPROVED subject anchor {args.subject} -> {args.asset}")
            return 0
        if args.location:
            if args.location not in continuity_data.get("locations", {}):
                raise ProductionError(f"Unknown continuity location: {args.location}")
            if args.location != node.location_id:
                raise ProductionError(
                    f"Cannot approve location {args.location} from {args.asset}: "
                    f"the source scene location is {node.location_id!r}"
                )
            registry.set_location(
                args.location,
                args.asset,
                output_sha256=output_sha256,
                fingerprint=fingerprint,
            )
            print(f"APPROVED location anchor {args.location} -> {args.asset}")
            return 0
    raise ProductionError("Specify either --subject or --location")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Crash-safe image + continuation + video producer for KathaMind scene plans"
    )
    sub = root.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Validate and print the zero-cost asset DAG")
    add_project(p_plan)
    p_plan.add_argument("--json", action="store_true")
    p_plan.set_defaults(func=cmd_plan)

    p_status = sub.add_parser("status", help="Show production manifest state")
    add_project(p_status)
    p_status.set_defaults(func=cmd_status)

    p_run = sub.add_parser("run", help="Generate or resume selected assets")
    add_project(p_run)
    p_run.add_argument("--scene", action="append", help="Limit to one or more scene ids")
    p_run.add_argument("--through", help="Run all scenes through this scene id")
    phase = p_run.add_mutually_exclusive_group()
    phase.add_argument("--images-only", action="store_true")
    phase.add_argument("--videos-only", action="store_true")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--image-provider", choices=("flow", "google"), default="flow")
    p_run.add_argument("--image-model", default="pro")
    p_run.add_argument("--video-provider", choices=("flow", "google"))
    p_run.add_argument("--video-model", default="omni_flash")
    p_run.add_argument(
        "--aspect-ratio",
        choices=("16:9", "9:16"),
        help="Safety override; must match session.visual.aspect_ratio (default: locked session value)",
    )
    p_run.add_argument("--flow-poll-seconds", type=float, default=3.0)
    p_run.add_argument("--flow-poll-timeout", type=float, default=900.0)
    p_run.set_defaults(func=cmd_run)

    p_retry = sub.add_parser("retry", help="Explicitly clear a failed/uncertain asset for retry")
    add_project(p_retry)
    p_retry.add_argument("--asset", required=True)
    p_retry.set_defaults(func=cmd_retry)

    p_anchor = sub.add_parser("anchor", help="Approve one generated image as a continuity anchor")
    add_project(p_anchor)
    p_anchor.add_argument("--asset", required=True)
    target = p_anchor.add_mutually_exclusive_group(required=True)
    target.add_argument("--subject")
    target.add_argument("--location")
    p_anchor.set_defaults(func=cmd_anchor)
    return root


def main() -> int:
    load_env_file(Path.home() / ".config/projects/.env")
    args = parser().parse_args()
    try:
        return int(args.func(args))
    except (PlanError, ProductionError, ProviderError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

