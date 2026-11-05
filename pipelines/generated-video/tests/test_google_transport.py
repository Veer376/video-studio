"""Verify the public API request contract without credentials or network calls."""
import base64
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.video.google import GoogleProvider, create_client


class GoogleTransportTests(unittest.TestCase):
    def test_explicit_key_selects_developer_without_adc(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fixture-not-a-secret"}, clear=True):
            with patch("google.genai.Client") as client, patch("google.auth.default") as adc:
                actual, label = create_client()
        self.assertIs(actual, client.return_value)
        self.assertEqual(label, "Gemini Developer API")
        client.assert_called_once_with(api_key="fixture-not-a-secret")
        adc.assert_not_called()

    def test_current_model_and_requested_duration_are_sent(self):
        client = Mock()
        client.interactions.create.return_value = SimpleNamespace(
            output_video=SimpleNamespace(data=base64.b64encode(b"fixture").decode()))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "clip.mp4"
            GoogleProvider(client=client).generate_video(
                prompt="A simple test scene.", output=target, duration=4)
            request = client.interactions.create.call_args.kwargs
            self.assertEqual(request["model"], "gemini-omni-1.1-flash")
            self.assertEqual(request["response_format"]["duration"], "4s")
            self.assertEqual(target.read_bytes(), b"fixture")
