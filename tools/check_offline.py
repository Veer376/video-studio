"""Run pipeline unittest discovery without credentials or provider sockets."""
from __future__ import annotations

import os
import socket
import unittest

for key in tuple(os.environ):
    if key.startswith(("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "CLOUDFLARE_", "CLOURFLARE_")) or key in {
        "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT",
        "GCP_PROJECT_ID", "STUDIO_ENV_FILE", "FLOW_AGENT_URL",
    }:
        os.environ.pop(key, None)

_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex


def _allowed(address):
    return (isinstance(address, tuple) and str(address[0]) in
            {"127.0.0.1", "::1", "localhost"} and address[1] != 8001)


def _connect(self, address):
    if not _allowed(address):
        raise RuntimeError("External and Flow connections are disabled during offline checks")
    return _original_connect(self, address)


def _connect_ex(self, address):
    if not _allowed(address):
        raise RuntimeError("External and Flow connections are disabled during offline checks")
    return _original_connect_ex(self, address)


socket.socket.connect = _connect
socket.socket.connect_ex = _connect_ex
suite = unittest.defaultTestLoader.discover("tests", pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
