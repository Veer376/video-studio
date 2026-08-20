from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from studio.core.config import load_production_config
from studio.core.paths import resolve_project_dir, script_path, src_dir
from studio.core.session import load_session
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
    image_provider: str | None = None,
    image_model: str | None = None,
    subtitles: bool | None = None,
    zoom: bool | None = None,
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
    image_override = image_provider is not None or image_model is not None
    render_override = subtitles is not None or zoom is not None
    if image_override and stage != "illustrate":
        raise PipelineError("image provider/model overrides apply only to illustrate")
    if render_override and stage != "render":
        raise PipelineError("subtitles/zoom overrides apply only to render")
    if validate_only and (image_override or render_override):
        raise PipelineError("production overrides cannot be used with --validate-only")

    current = stage_state(resolved, stage)
    if validate_only:
        if current.complete:
            print(f"OK {stage} is complete.")
            return
        raise PipelineError(f"{stage} is incomplete: {', '.join(current.missing)}")

    if current.complete and not force and not (
        stage == "illustrate" and illustration_phase == "characters"
    ):
        if image_override or render_override:
            raise PipelineError(
                f"{stage} is already complete; use --force to apply configuration overrides"
            )
        print(f"OK {stage} already complete. Use --force to rerun.")
        return

    if image_override and not force:
        if illustration_phase == "characters":
            cached_images = list((resolved / "assets" / "characters").glob("*.png"))
        else:
            cached_images = list((resolved / "images").glob("*.png"))
        if cached_images:
            raise PipelineError(
                "illustrate has cached images; use --force to apply provider/model overrides consistently"
            )
    if render_override and not force:
        cached_clips = list((resolved / "temp" / "scenes").glob("*.mp4"))
        if cached_clips:
            raise PipelineError(
                "render has cached scene clips; use --force to apply subtitles/zoom overrides"
            )

    if stage == "voice":
        args = ("--force",) if force else ()
        _run_script(resolved, "pipeline_scripts/narration.py", *args)
    elif stage == "illustrate":
        args = ("--phase", illustration_phase)
        if image_provider is not None:
            args += ("--provider", image_provider)
        if image_model is not None:
            args += ("--model", image_model)
        if force:
            args += ("--force",)
        _run_script(resolved, "images/illustrate.py", *args)
        if illustration_phase == "characters":
            return
    elif stage == "render":
        try:
            production = load_production_config(
                load_session(resolved),
                subtitles=subtitles,
                zoom=zoom,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise PipelineError(str(exc)) from exc
        final_args = ("--force",) if force else ()
        scene_args = final_args
        if production.subtitles:
            _run_script(resolved, "subtitles/subtitles.py")
        else:
            scene_args += ("--skip-subtitles",)
        if not production.zoom:
            scene_args += ("--no-motion",)
        _run_script(resolved, "rendering/scenes.py", *scene_args)
        _run_script(resolved, "rendering/final.py", *final_args)

    after = stage_state(resolved, stage)
    if not after.complete:
        raise PipelineError(f"{stage} did not complete: {', '.join(after.missing)}")
    update_status(resolved, f"{stage}_complete")


def run_pipeline(
    project_dir: str | Path,
    *,
    from_stage: str | None = None,
    force_stage: str | list[str] | tuple[str, ...] | None = None,
    force: bool = False,
    image_provider: str | None = None,
    image_model: str | None = None,
    subtitles: bool | None = None,
    zoom: bool | None = None,
) -> None:
    resolved = resolve_project_dir(project_dir)
    if from_stage and from_stage not in STAGES:
        raise PipelineError(f"Unknown --from stage: {from_stage}")
    force_stages = {force_stage} if isinstance(force_stage, str) else set(force_stage or ())
    unknown_force_stages = force_stages - set(STAGES)
    if unknown_force_stages:
        raise PipelineError(f"Unknown --force-stage: {', '.join(sorted(unknown_force_stages))}")
    if from_stage == "render" and (image_provider is not None or image_model is not None):
        raise PipelineError("image provider/model overrides cannot be used when starting from render")

    start_index = STAGES.index(from_stage) if from_stage else 0
    for stage in STAGES[start_index:]:
        stage_force = force or stage in force_stages
        run_stage(
            resolved,
            stage,
            force=stage_force,
            image_provider=image_provider if stage == "illustrate" else None,
            image_model=image_model if stage == "illustrate" else None,
            subtitles=subtitles if stage == "render" else None,
            zoom=zoom if stage == "render" else None,
        )
