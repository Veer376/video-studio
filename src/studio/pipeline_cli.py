from __future__ import annotations

import argparse
import sys
from pathlib import Path

from studio.pipeline_scripts.image_story import PipelineError, print_status, run_pipeline, run_stage
from studio.pipeline_scripts.narration import VOICE_STEPS, run_voice_step


PIPELINE_CHOICES = ("image-story",)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="story-video")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Inspect resumable pipeline state for a project.")
    status.add_argument("project_dir", type=Path)

    run = sub.add_parser("run", help="Run the default image-story pipeline.")
    run.add_argument("project_dir", type=Path)
    run.add_argument("--from", dest="from_stage", choices=["voice", "illustrate", "render"])
    run.add_argument("--force-stage", choices=["voice", "illustrate", "render"])
    run.add_argument("--force", action="store_true")

    pipeline = sub.add_parser("pipeline", help="Run a named pipeline.")
    pipeline.add_argument("pipeline_name", choices=PIPELINE_CHOICES)
    pipeline.add_argument("project_dir", type=Path)
    pipeline.add_argument("--from", dest="from_stage", choices=["voice", "illustrate", "render"])
    pipeline.add_argument("--force-stage", choices=["voice", "illustrate", "render"])
    pipeline.add_argument("--force", action="store_true")

    stage = sub.add_parser("stage", help="Run or validate one image-story stage.")
    stage.add_argument("stage_name", choices=["voice", "illustrate", "render"])
    stage.add_argument("project_dir", type=Path)
    stage.add_argument("--force", action="store_true")
    stage.add_argument("--missing-only", action="store_true", help="Default behavior; kept for explicit retry commands.")
    stage.add_argument("--validate-only", action="store_true")

    retry = sub.add_parser("retry", help="Retry one stage. Defaults to missing-only behavior.")
    retry.add_argument("project_dir", type=Path)
    retry.add_argument("--stage", dest="stage_name", required=True, choices=["voice", "illustrate", "render"])
    retry.add_argument("--force", action="store_true")
    retry.add_argument("--missing-only", action="store_true")

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
            run_pipeline(args.project_dir, from_stage=args.from_stage, force_stage=args.force_stage, force=args.force)
        elif args.command == "pipeline":
            run_pipeline(args.project_dir, from_stage=args.from_stage, force_stage=args.force_stage, force=args.force)
        elif args.command == "stage":
            run_stage(args.project_dir, args.stage_name, force=args.force, validate_only=args.validate_only)
        elif args.command == "retry":
            run_stage(args.project_dir, args.stage_name, force=args.force)
        elif args.command == "voice-step":
            run_voice_step(args.project_dir, args.step_name, force=args.force, unit_id=args.unit)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
