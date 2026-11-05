from __future__ import annotations

import argparse
import sys
from pathlib import Path

from studio.pipeline_scripts.production import PipelineError, print_status, run_pipeline, run_stage
from studio.pipeline_scripts.narration import VOICE_STEPS, run_voice_step


def _add_production_overrides(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--image-provider",
        choices=("cloudflare", "flow", "google"),
        help="Temporarily override the configured illustration provider.",
    )
    parser.add_argument(
        "--image-model",
        help="Temporarily override the configured illustration model.",
    )
    parser.add_argument(
        "--subtitles",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Temporarily enable or disable rendered subtitles.",
    )
    parser.add_argument(
        "--zoom",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Temporarily enable or disable Ken Burns motion.",
    )
    parser.add_argument(
        "--closing-fade",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Temporarily enable or disable 2s tail extension and closing fade out.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="story-video")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Inspect resumable pipeline state for a project.")
    status.add_argument("project_dir", type=Path)

    run = sub.add_parser("run", help="Run the default production flow.")
    run.add_argument("project_dir", type=Path)
    run.add_argument("--from", dest="from_stage", choices=["voice", "illustrate", "render"])
    run.add_argument(
        "--force-stage",
        choices=["voice", "illustrate", "render"],
        action="append",
        help="Force one stage; repeat to force multiple stages.",
    )
    run.add_argument("--force", action="store_true")
    _add_production_overrides(run)

    stage = sub.add_parser("stage", help="Run or validate one production stage.")
    stage.add_argument("stage_name", choices=["voice", "illustrate", "render"])
    stage.add_argument("project_dir", type=Path)
    stage.add_argument("--force", action="store_true")
    stage.add_argument("--missing-only", action="store_true", help="Default behavior; kept for explicit retry commands.")
    stage.add_argument("--validate-only", action="store_true")
    stage.add_argument(
        "--illustration-phase",
        choices=("all", "characters", "scenes"),
        default="all",
        help="For illustrate: run both phases, canonical characters only, or scenes only.",
    )
    _add_production_overrides(stage)

    retry = sub.add_parser("retry", help="Retry one stage. Defaults to missing-only behavior.")
    retry.add_argument("project_dir", type=Path)
    retry.add_argument("--stage", dest="stage_name", required=True, choices=["voice", "illustrate", "render"])
    retry.add_argument("--force", action="store_true")
    retry.add_argument("--missing-only", action="store_true")
    _add_production_overrides(retry)

    voice_step = sub.add_parser("voice-step", help="Run one internal voice step without rerunning the others.")
    voice_step.add_argument("step_name", choices=VOICE_STEPS)
    voice_step.add_argument("project_dir", type=Path)
    voice_step.add_argument("--force", action="store_true")
    voice_step.add_argument("--unit", help="Transcribe only one narration unit, such as unit-003.")

    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            print_status(args.project_dir)
        elif args.command == "run":
            run_pipeline(
                args.project_dir,
                from_stage=args.from_stage,
                force_stage=args.force_stage,
                force=args.force,
                image_provider=args.image_provider,
                image_model=args.image_model,
                subtitles=args.subtitles,
                zoom=args.zoom,
                closing_fade=args.closing_fade,
            )
        elif args.command == "stage":
            run_stage(
                args.project_dir,
                args.stage_name,
                force=args.force,
                validate_only=args.validate_only,
                illustration_phase=args.illustration_phase,
                image_provider=args.image_provider,
                image_model=args.image_model,
                subtitles=args.subtitles,
                zoom=args.zoom,
                closing_fade=args.closing_fade,
            )
        elif args.command == "retry":
            run_stage(
                args.project_dir,
                args.stage_name,
                force=args.force,
                image_provider=args.image_provider,
                image_model=args.image_model,
                subtitles=args.subtitles,
                zoom=args.zoom,
                closing_fade=args.closing_fade,
            )
        elif args.command == "voice-step":
            run_voice_step(args.project_dir, args.step_name, force=args.force, unit_id=args.unit)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
