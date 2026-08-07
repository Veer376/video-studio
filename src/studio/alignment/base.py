"""
Base interface and shared Devanagari text-processing utilities for scene timestamp alignment.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Protocol, Sequence, TypedDict


class AlignmentLogEntry(TypedDict, total=False):
    scene_id: str
    status: str
    start_matched: bool
    end_matched: bool
    anchor_start_idx: int
    anchor_end_idx: int
    start_time: float
    end_time: float
    fingerprint: list[str]
    tail: list[str]


class AlignmentEngine(Protocol):
    """Protocol for interchangeable scene timestamp alignment engines."""
    def align_scenes(
        self,
        scenes: Sequence[dict[str, Any]],
        words: Sequence[dict[str, Any]],
        duration: float,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        ...


_MORPH_MAP: dict[str, str] = {
    "ये": "यह",   "यह": "यह",
    "वो": "वह",   "वह": "वह",
    "गए": "गया",  "गया": "गया",
    "किए": "किया", "किया": "किया",
    "नही": "नहीं", "नहीं": "नहीं",
    "हुई": "हुआ",  "हुए": "हुआ",  "हुआ": "हुआ",
}


def content_words(text: str) -> list[str]:
    """
    Extract spoken content words from scene text, preserving digit tokens.
    Strips symbols, stage directions, punctuation. Keeps digits as separate tokens.
    Sub-2-char non-digit tokens are dropped.
    """
    clean = re.sub(r'\[.*?\]|\(.*?\)', '', text)
    clean = re.sub(r'[>\*\"\'.!?,।—…:;\-\[\]()]', ' ', clean)
    clean = unicodedata.normalize('NFC', clean)

    tokens = []
    for token in clean.split():
        t = token.strip()
        if t.isdigit():
            tokens.append(t)
        elif len(t) >= 2:
            tokens.append(t)
    return tokens


def normalize_for_match(s: str) -> str:
    """
    Normalize a Devanagari string for consonant-skeleton comparison.
    1. Applies morphological equivalence mapping on the raw string.
    2. Strips all Devanagari dependent vowel marks (matras U+093E–U+094F) and nukta.
    3. Applies morphological equivalence mapping again on the stripped string.
    """
    s = re.sub(r'[>*"\'`.!?,।—…:;\-\[\]()0-9]', '', s)
    s = unicodedata.normalize('NFC', s).strip()
    s = _MORPH_MAP.get(s, s)
    s = s.replace('\u094d', '').replace('\u093c', '')
    result = []
    for ch in s:
        cp = ord(ch)
        if 0x093E <= cp <= 0x094F or cp in (0x0902, 0x0903):
            continue
        result.append(ch)
    s = ''.join(result).strip()
    return _MORPH_MAP.get(s, s)


def bigram_similarity(a: str, b: str) -> float:
    """Character bigram Jaccard similarity over consonant skeleton normalized strings."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    bigrams_a = {a[i:i+2] for i in range(len(a) - 1)}
    bigrams_b = {b[i:i+2] for i in range(len(b) - 1)}
    if not bigrams_a or not bigrams_b:
        return 1.0 if a == b else 0.0
    intersection = bigrams_a & bigrams_b
    union = bigrams_a | bigrams_b
    return len(intersection) / len(union)


def normalize_scene_intervals(scenes: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    """Ensure monotonic non-overlapping scene boundaries spanning 0 to duration continuously."""
    if not scenes:
        return scenes
    starts = [float(scene.get("start_time") or 0.0) for scene in scenes]
    starts[0] = 0.0
    for idx in range(1, len(starts)):
        minimum_start = starts[idx - 1] + 0.1
        if starts[idx] < minimum_start:
            starts[idx] = minimum_start
        starts[idx] = min(starts[idx], max(duration - 0.1, minimum_start))

    for idx, scene in enumerate(scenes):
        scene["start_time"] = round(starts[idx], 3)
        if idx == len(scenes) - 1:
            scene["end_time"] = round(duration, 3)
        else:
            scene["end_time"] = round(starts[idx + 1], 3)

    return scenes
