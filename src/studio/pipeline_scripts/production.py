from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from studio.core.paths import resolve_project_dir, script_path, src_dir
from studio.core.session import update_status
from studio.core.state import STAGES, all_states, stage_state


class PipelineError(RuntimeError):
    pass


def _run_script(project_dir: Path, script_name: str, *extra_args: str) -> None:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(src_dir()) + (os.pathsep + existing if existing else "")
    cmd = [
        sys.executable,
        str(script_path(script_name)),
        "--project-dir",
        str(project_dir),
        *extra_args,
    ]
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        raise PipelineError(f"{script_name} failed with exit code {result.returncode}")


def print_status(project_dir: str | Path) -> None:
    resolved = resolve_project_dir(project_dir)
    print(f"Project: {resolved}")
    for state in all_states(resolved):
        marker = "complete" if state.complete else "incomplete"
        print(f"- {state.name}: {marker}")
        if state.missing:
            for item in state.missing:
                print(f"  missing: {item}")


def run_stage(
    project_dir: str | Path,
    stage: str,
    *,
    force: bool = False,
    validate_only: bool = False,
    illustration_phase: str = "all",
) -> None:
    resolved = resolve_project_dir(project_dir)
    if stage not in STAGES:
        raise PipelineError(f"Unknown production stage: {stage}")
    if illustration_phase not in ("all", "characters", "scenes"):
        raise PipelineError(f"Unknown illustration phase: {illustration_phase}")
    if stage != "illustrate" and illustration_phase != "all":
        raise PipelineError("--illustration-phase is valid only for the illustrate stage")
    if validate_only and illustration_phase != "all":
        raise PipelineError("partial illustration phases cannot use --validate-only")

    current = stage_state(resolved, stage)
    if validate_only:
        if current.complete:
            print(f"OK {stage} is complete.")
            return
        raise PipelineError(f"{stage} is incomplete: {', '.join(current.missing)}")

    if current.complete and not force and not (
        stage == "illustrate" and illustration_phase == "characters"
    ):
        print(f"OK {stage} already complete. Use --force to rerun.")
        return

    if stage == "voice":
        args = ("--force",) if force else ()
        _run_script(resolved, "pipeline_scripts/narration.py", *args)
    elif stage == "illustrate":
        args = ("--phase", illustration_phase)
        if force:
            args += ("--force",)
        _run_script(resolved, "images/cloudflare_image_gen.py", *args)
        if illustration_phase == "characters":
            return
    elif stage == "render":
        args = ("--force",) if force else ()
        _run_script(resolved, "subtitles/subtitles.py")
        _run_script(resolved, "rendering/scenes.py", *args)
        _run_script(resolved, "rendering/final.py", *args)

    after = stage_state(resolved, stage)
    if not after.complete:
        raise PipelineError(f"{stage} did not complete: {', '.join(after.missing)}")
    update_status(resolved, f"{stage}_complete")


def run_pipeline(
    project_dir: str | Path,
    *,
    from_stage: str | None = None,
    force_stage: str | None = None,
    force: bool = False,
) -> None:
    resolved = resolve_project_dir(project_dir)
    if from_stage and from_stage not in STAGES:
        raise PipelineError(f"Unknown --from stage: {from_stage}")
    if force_stage and force_stage not in STAGES:
        raise PipelineError(f"Unknown --force-stage: {force_stage}")

    start_index = STAGES.index(from_stage) if from_stage else 0
    for stage in STAGES[start_index:]:
        stage_force = force or stage == force_stage
        run_stage(resolved, stage, force=stage_force)
