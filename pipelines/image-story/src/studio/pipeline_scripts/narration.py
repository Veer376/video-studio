"""Orchestrate the three resumable internal voice steps."""
from __future__ import annotations

import argparse
from pathlib import Path

from studio.alignment.units import align_narration_units
from studio.transcription.units import transcribe_units
from studio.voice.units import MAX_UNIT_WORDS, generate_narration_units, group_scenes


VOICE_STEPS = ("narrate", "transcribe", "align")


def run_voice_step(
    project_dir: str | Path,
    step: str,
    *,
    force: bool = False,
    unit_id: str | None = None,
    max_unit_words: int = MAX_UNIT_WORDS,
) -> None:
    if step == "narrate":
        if unit_id:
            raise ValueError("--unit is supported only by the transcribe step")
        generate_narration_units(project_dir, force=force, max_unit_words=max_unit_words)
    elif step == "transcribe":
        transcribe_units(project_dir, force=force, unit_id=unit_id)
    elif step == "align":
        if unit_id:
            raise ValueError("--unit is supported only by the transcribe step")
        align_narration_units(project_dir)
    else:
        raise ValueError(f"Unknown voice step: {step}")


def run_narration(
    project_dir: str | Path,
    *,
    force: bool = False,
    max_unit_words: int = MAX_UNIT_WORDS,
) -> None:
    generate_narration_units(project_dir, force=force, max_unit_words=max_unit_words)
    transcribe_units(project_dir, force=force)
    align_narration_units(project_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build narration, transcription, and scene timings")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--step", choices=VOICE_STEPS)
    parser.add_argument("--unit")
    args = parser.parse_args()
    if args.step:
        run_voice_step(args.project_dir, args.step, force=args.force, unit_id=args.unit)
    else:
        run_narration(args.project_dir, force=args.force)


if __name__ == "__main__":
    main()
