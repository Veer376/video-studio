"""Align independently transcribed narration units to their source scenes."""
from __future__ import annotations

import copy
from pathlib import Path

from studio.alignment.base import normalize_for_match, normalize_scene_intervals
from studio.alignment.dp import align_text_dp
from studio.core.io import read_json, write_json
from studio.transcription.units import TRANSCRIPTION_VERSION, validate_transcription


def align_narration_units(project_dir: str | Path) -> dict:
    project_dir = Path(project_dir).resolve()
    scenes_path = project_dir / "scenes.json"
    manifest_path = project_dir / "audio" / "narration" / "manifest.json"
    if not scenes_path.exists() or not manifest_path.exists():
        raise FileNotFoundError("alignment requires scenes.json and narration manifest")

    scenes_data = read_json(scenes_path)
    scenes = list(scenes_data.get("scenes") or [])
    scenes_by_id = {scene.get("id"): scene for scene in scenes}
    units = list(read_json(manifest_path).get("units") or [])
    all_words: list[dict] = []
    provider_units: list[dict] = []
    language: str | None = None
    offset = 0.0
    print(f"→ Alignment: {len(units)} independently timed unit(s)")

    for unit in units:
        transcription_path = project_dir / "audio" / "transcription" / f"{unit['id']}.json"
        if not transcription_path.exists():
            raise FileNotFoundError(f"Missing transcription for {unit['id']}")
        transcription = read_json(transcription_path)
        if language is None:
            language = transcription.get("language")
        duration = float(unit["duration"])
        valid, reasons = validate_transcription(transcription, unit["text"], duration)
        if not valid or transcription.get("transcription_version") != TRANSCRIPTION_VERSION:
            raise RuntimeError(f"Invalid transcription for {unit['id']}: {', '.join(reasons)}")

        group = []
        for scene_id in unit["scene_ids"]:
            if scene_id not in scenes_by_id:
                raise RuntimeError(f"Narration manifest references missing scene: {scene_id}")
            group.append(copy.deepcopy(scenes_by_id[scene_id]))
        words = list(transcription.get("words") or [])
        if len(group) == 1:
            aligned = group
            aligned[0]["start_time"] = 0.0
            aligned[0]["end_time"] = duration
        else:
            # Exact transcripts need no fuzzy search: preserve authored word
            # ownership, including short tokens that the fuzzy scorer drops.
            expected = [normalize_for_match(token) for scene in group
                        for token in str(scene.get("text", "")).split()]
            actual = [normalize_for_match(str(word.get("word", ""))) for word in words]
            if expected and all(expected) and expected == actual:
                aligned = group
                cursor = 0
                for scene in aligned:
                    count = len(str(scene.get("text", "")).split())
                    scene["start_time"] = float(words[cursor]["start"])
                    cursor += count
                    scene["end_time"] = float(words[cursor - 1]["end"])
            else:
                aligned, _ = align_text_dp(group, words, duration)
            aligned = normalize_scene_intervals(aligned, duration)

        for local_scene in aligned:
            target = scenes_by_id[local_scene["id"]]
            target["start_time"] = round(offset + float(local_scene["start_time"]), 3)
            target["end_time"] = round(offset + float(local_scene["end_time"]), 3)
        for word in words:
            all_words.append({
                "word": word.get("word", ""),
                "start": round(offset + float(word["start"]), 3),
                "end": round(offset + float(word["end"]), 3),
            })
        provider_units.append({
            "id": unit["id"],
            "provider": transcription.get("provider"),
            "model": transcription.get("model"),
            "start": round(offset, 3),
            "end": round(offset + duration, 3),
        })
        offset += duration

    timestamps = {
        "duration": round(offset, 3),
        "language": language,
        "word_count": len(all_words),
        "words": all_words,
        "units": provider_units,
    }
    # The mixed-media renderer uses explicit inclusive word ranges. Derive them
    # from the same time-based assignment used by subtitle rendering.
    from studio.subtitles.subtitles import assign_words_to_scenes

    assignments = assign_words_to_scenes(all_words, scenes)
    cursor = 0
    for index, scene in enumerate(scenes):
        assigned = assignments[index]
        if not assigned:
            raise RuntimeError(f"No aligned words for scene {scene['id']}")
        if assigned != all_words[cursor:cursor + len(assigned)]:
            raise RuntimeError(f"Non-contiguous word assignment for scene {scene['id']}")
        scene["word_start"] = cursor
        cursor += len(assigned)
        scene["word_end"] = cursor - 1
    if cursor != len(all_words):
        raise RuntimeError("Some transcription words fall outside the aligned scene intervals")

    write_json(project_dir / "audio" / "timestamps.json", timestamps)
    scenes_data["scenes"] = scenes
    write_json(scenes_path, scenes_data)
    print(f"✓ Scene timestamps complete ({offset:.2f}s)")
    return timestamps
