import json
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from studio.alignment.units import align_narration_units
from studio.transcription.units import transcribe_units, validate_transcription
from studio.voice.units import generate_narration_units, group_scenes


def _write_one_second_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8_000)
        output.writeframes(b"\x00\x00" * 8_000)


def _project(path: Path) -> None:
    (path / "session.json").write_text(
        json.dumps({"voice": {"language": "hi-IN"}}), encoding="utf-8"
    )
    (path / "scenes.json").write_text(
        json.dumps({
            "scenes": [
                {"id": "scene-001", "text": "पहला सुंदर दृश्य"},
                {"id": "scene-002", "text": "दूसरा सरल दृश्य"},
            ]
        }),
        encoding="utf-8",
    )


def _valid_result(text: str = "पहला सुंदर दृश्य") -> dict:
    words = text.split()
    return {
        "duration": 1.0,
        "language": "hi",
        "word_count": len(words),
        "words": [
            {"word": word, "start": round(index * 0.25, 2), "end": round((index + 1) * 0.25, 2)}
            for index, word in enumerate(words)
        ],
    }


class NarrationPipelineTests(unittest.TestCase):
    def test_group_scenes_keeps_every_scene_whole(self):
        scenes = [
            {"id": "scene-001", "text": "one two three"},
            {"id": "scene-002", "text": "four five three"},
            {"id": "scene-003", "text": "six seven"},
        ]
        groups = group_scenes(scenes, max_words=5)
        self.assertEqual(
            [["scene-001"], ["scene-002", "scene-003"]],
            [[scene["id"] for scene in group] for group in groups],
        )

    @patch("studio.voice.units.load_api_keys", return_value=["gemini-key"])
    @patch("studio.voice.units.call_gemini_tts")
    def test_narration_writes_durable_units_and_manifest(self, mock_tts, _mock_keys):
        mock_tts.side_effect = lambda _key, _model, _voice, _text, output: _write_one_second_wav(output)
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _project(project_dir)
            manifest = generate_narration_units(project_dir, max_unit_words=1)
            self.assertEqual(2, len(manifest["units"]))
            self.assertTrue((project_dir / "audio/narration/unit-001.wav").exists())
            self.assertTrue((project_dir / "audio/narration/manifest.json").exists())
            self.assertTrue((project_dir / "audio/narration.wav").exists())
            self.assertEqual(2, mock_tts.call_count)

    @patch("studio.transcription.units.load_openai_key", return_value="openai-key")
    @patch("studio.transcription.units.load_groq_keys", return_value=["groq-key"])
    @patch("studio.transcription.units.extract_timestamps_openai")
    @patch("studio.transcription.units.extract_timestamps_single")
    def test_invalid_groq_falls_back_to_openai_whisper_1(
        self, mock_groq, mock_openai, _mock_groq_keys, _mock_openai_key
    ):
        mock_groq.return_value = {
            "duration": 1.0,
            "word_count": 1,
            "words": [{"word": "पहला", "start": 0.0, "end": 0.2}],
        }
        mock_openai.return_value = _valid_result()
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _project(project_dir)
            audio_path = project_dir / "audio/narration/unit-001.wav"
            _write_one_second_wav(audio_path)
            manifest = {
                "units": [{
                    "id": "unit-001",
                    "scene_ids": ["scene-001"],
                    "text": "पहला सुंदर दृश्य",
                    "input_hash": "hash-1",
                    "audio_path": "audio/narration/unit-001.wav",
                    "duration": 1.0,
                }]
            }
            (project_dir / "audio/narration/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            results = transcribe_units(project_dir)
            self.assertEqual("openai", results[0]["provider"])
            self.assertEqual("whisper-1", results[0]["model"])
            self.assertEqual(3, mock_groq.call_count)
            self.assertEqual("whisper-large-v3", mock_groq.call_args.kwargs["model_name"])
            self.assertEqual(1, mock_openai.call_count)

    def test_alignment_offsets_units_and_writes_final_contract(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            _project(project_dir)
            narration_dir = project_dir / "audio/narration"
            transcription_dir = project_dir / "audio/transcription"
            narration_dir.mkdir(parents=True)
            transcription_dir.mkdir(parents=True)
            manifest = {"units": []}
            for index, (scene_id, text) in enumerate([
                ("scene-001", "पहला सुंदर दृश्य"),
                ("scene-002", "दूसरा सरल दृश्य"),
            ], start=1):
                unit_id = f"unit-{index:03d}"
                manifest["units"].append({
                    "id": unit_id,
                    "scene_ids": [scene_id],
                    "text": text,
                    "input_hash": f"hash-{index}",
                    "audio_path": f"audio/narration/{unit_id}.wav",
                    "duration": 1.0,
                })
                result = _valid_result(text)
                result.update({
                    "provider": "groq",
                    "model": "whisper-large-v3",
                    "input_hash": f"hash-{index}",
                    "transcription_version": 1,
                })
                (transcription_dir / f"{unit_id}.json").write_text(json.dumps(result), encoding="utf-8")
            (narration_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            timestamps = align_narration_units(project_dir)
            scenes = json.loads((project_dir / "scenes.json").read_text())["scenes"]
            self.assertEqual(2.0, timestamps["duration"])
            self.assertEqual([0.0, 1.0], [scene["start_time"] for scene in scenes])
            self.assertEqual([1.0, 2.0], [scene["end_time"] for scene in scenes])
            self.assertEqual([0.0, 1.0], [unit["start"] for unit in timestamps["units"]])

    def test_validation_rejects_early_truncation(self):
        valid, reasons = validate_transcription(
            {"words": [{"word": "पहला", "start": 0.0, "end": 0.2}]},
            "पहला सुंदर दृश्य",
            4.0,
        )
        self.assertFalse(valid)
        self.assertTrue(any("before audio" in reason for reason in reasons))


if __name__ == "__main__":
    unittest.main()
