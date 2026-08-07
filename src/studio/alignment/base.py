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


HINDI_NUMBERS_1_TO_100: dict[str, str] = {
    "1": "एक", "2": "दो", "3": "तीन", "4": "चार", "5": "पांच", "6": "छह", "7": "सात", "8": "आठ", "9": "नौ", "10": "दस",
    "11": "ग्यारह", "12": "बारह", "13": "तेरह", "14": "चौदह", "15": "पंद्रह", "16": "सोलह", "17": "सत्रह", "18": "अठारह", "19": "उन्नीस", "20": "बीस",
    "21": "इक्कीस", "22": "बाईस", "23": "तेईस", "24": "चौबीस", "25": "पच्चीस", "26": "छब्बीस", "27": "सत्ताईस", "28": "अट्ठाईस", "29": "उनतीस", "30": "तीस",
    "31": "इकतीस", "32": "बत्तीस", "33": "तैंतीस", "34": "चौंतीस", "35": "पैंतीस", "36": "छत्तीस", "37": "सैंतीस", "38": "अड़तीस", "39": "उनतालीस", "40": "चालीस",
    "41": "इकतालीस", "42": "बयालीस", "43": "तैंतालीस", "44": "चवालीस", "45": "पैंतालीस", "46": "छियालीस", "47": "सैंतालीस", "48": "अड़तालीस", "49": "उनचास", "50": "पचास",
    "51": "इक्कावन", "52": "बावन", "53": "तिर्पन", "54": "चौवन", "55": "पचपन", "56": "छप्पन", "57": "सत्तावन", "58": "अट्टावन", "59": "उनसठ", "60": "साठ",
    "61": "एकसठ", "62": "बासठ", "63": "तिरसठ", "64": "चौंसठ", "65": "पैंसठ", "66": "छियासठ", "67": "सरसठ", "68": "अड़सठ", "69": "उनहत्तर", "70": "सत्तर",
    "71": "इकहत्तर", "72": "बहत्तर", "73": "तिहत्तर", "74": "चौहत्तर", "75": "पचहत्तर", "76": "छिहत्तर", "77": "सतहत्तर", "78": "अठहत्तर", "79": "उनासी", "80": "अस्सी",
    "81": "इक्यासी", "82": "बयासी", "83": "तिरासी", "84": "चौरासी", "85": "पचासी", "86": "छियासी", "87": "सत्तासी", "88": "अट्ठासी", "89": "नवासी", "90": "नब्बे",
    "91": "इकानवे", "92": "बानवे", "93": "तिरानवे", "94": "चौरानवे", "95": "पचानवे", "96": "छियानवे", "97": "संतानवे", "98": "अठानवे", "99": "निन्न्यानवे", "100": "सौ"
}

WORD_TO_DIGIT_MAP: dict[str, str] = {val: key for key, val in HINDI_NUMBERS_1_TO_100.items()}
# Add common spelling variants
WORD_TO_DIGIT_MAP.update({
    "पाँच": "5", "छे": "6", "अठारह": "18", "इक्कतीस": "31", "चालीस": "40",
    "इक्तालीस": "41", "सैंतालीस": "47", "अड़तालीस": "48", "पाँच": "5",
    "neuroscience": "neuroscience", "overthinking": "overthinking"
})

_MORPH_MAP: dict[str, str] = {
    "ये": "यह",   "यह": "यह",
    "वो": "वह",   "वह": "वह",
    "गए": "गया",  "गया": "गया",
    "किए": "किया", "किया": "किया",
    "नही": "नहीं", "नहीं": "नहीं",
    "हुई": "हुआ",  "हुए": "हुआ",  "हुआ": "हुआ",
    "neuroscience": "न्यूरोसाइंस", "न्यूरोसाइंस": "न्यूरोसाइंस",
    "overthinking": "ओवरथिंकिंग", "ओवरथिंकिंग": "ओवरथिंकिंग",
}

# Populate _MORPH_MAP bidirectionally for all 1-100 numbers
for num_str, word in HINDI_NUMBERS_1_TO_100.items():
    _MORPH_MAP[num_str] = word
    _MORPH_MAP[word] = word



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


def clean_hindi_char_count(text: str) -> int:
    """Extract clean Devanagari/Hindi character count excluding whitespace and punctuation."""
    clean = re.sub(r'\[.*?\]|\(.*?\)', '', text)
    clean = re.sub(r'[>\*\"\'.!?,।—…:;\-\[\]()\s]', '', clean)
    return len(clean)


def apply_character_weighted_fallback(
    scenes: list[dict[str, Any]],
    log_entries: list[dict[str, Any]],
    duration: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Shared post-processing pass to allocate valid display windows for contiguous FALLBACK scene blocks
    proportionally by clean Hindi character counts between verified predecessor and successor anchors.
    Ensures verified scene anchors are NEVER pushed or overlapped.
    """
    n = len(scenes)
    i = 0

    while i < n:
        if log_entries[i].get("status") == "FALLBACK":
            # Find contiguous block of FALLBACK scenes [i .. j-1]
            j = i
            while j < n and log_entries[j].get("status") == "FALLBACK":
                j += 1

            # Predecessor anchor: verified end_time of preceding OK scene (or 0.0)
            start_anchor = scenes[i-1]["end_time"] if i > 0 and log_entries[i-1].get("status") == "OK" else 0.0
            # Successor anchor: verified start_time of succeeding OK scene (or total audio duration)
            end_anchor = scenes[j]["start_time"] if j < n and log_entries[j].get("status") == "OK" else duration

            # Ensure end_anchor is monotonically greater than start_anchor with minimum scene display duration
            min_required_dur = max(3.0, (j - i) * 2.5)
            if end_anchor < start_anchor + min_required_dur:
                end_anchor = start_anchor + min_required_dur
                if j < n:
                    scenes[j]["start_time"] = end_anchor
                    log_entries[j]["start_time"] = end_anchor

            gap_duration = max(min_required_dur, end_anchor - start_anchor)

            # Calculate character weights for missing scenes in block
            block_weights = [max(1, clean_hindi_char_count(scenes[k].get("text", ""))) for k in range(i, j)]
            total_weight = sum(block_weights)

            curr_t = start_anchor
            for k_idx, k in enumerate(range(i, j)):
                portion = block_weights[k_idx] / total_weight
                scene_dur = gap_duration * portion
                st = round(curr_t, 3)
                et = round(curr_t + scene_dur, 3)
                if k == j - 1:
                    et = round(end_anchor, 3)

                scenes[k]["start_time"] = st
                scenes[k]["end_time"] = et
                log_entries[k]["start_time"] = st
                log_entries[k]["end_time"] = et
                log_entries[k]["timing_source"] = "interpolated"
                log_entries[k]["timing_confidence"] = "low"

                curr_t = et

            i = j
        else:
            i += 1

    return scenes, log_entries

