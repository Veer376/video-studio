"""
Align Groq word timestamps to scenes using text-anchored fuzzy matching.
Updates scenes.json in-place with start_time and end_time per scene,
and writes an alignment_log.json in the audio/ directory for inspection.

Usage:
    python3 -m studio.alignment.anchored --project-dir library/2026-08-01_krishna-motivation
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from studio.alignment.base import (
    AlignmentEngine,
    bigram_similarity,
    content_words,
    normalize_for_match,
    normalize_scene_intervals,
)


def is_digit_token(s: str) -> bool:
    """Return True if the token is a pure digit string (e.g. '30', '5', '100')."""
    return s.strip().isdigit()


def best_token_match(groq_words: list, i: int, fp_word: str) -> tuple[float, int]:
    """
    Try merging 1, 2, or 3 consecutive Groq tokens and return the best
    (similarity_score, tokens_consumed) for fp_word.
    Both sides are normalized via normalize_for_match() (consonant skeleton)
    before comparison, which handles matra-drop errors automatically.
    """
    best_score = 0.0
    best_n = 1
    fp_norm = normalize_for_match(fp_word)
    for n in [1, 2, 3]:
        if i + n > len(groq_words):
            break
        merged = "".join(groq_words[i + k].get("word", "") for k in range(n))
        merged_norm = normalize_for_match(merged)
        score = bigram_similarity(fp_norm, merged_norm)
        if score > best_score:
            best_score = score
            best_n = n
    return best_score, best_n


def normalize_groq_word(word_obj: dict) -> str:
    """Normalize a single Groq word token (kept for backward-compat)."""
    return normalize_for_match(word_obj.get("word", ""))


def search_forward(groq_words: list, from_idx: int, fingerprint: list[str], stop_at: int) -> tuple[int, bool]:
    """
    Search forward in groq_words from from_idx up to stop_at (exclusive)
    matching fingerprint tokens.

    Handles:
    - Digit tokens in fingerprint as positional wildcards (consume 1 Groq word, no score requirement)
    - Compound word splitting: tries merging up to 3 consecutive Groq tokens for each fp word
    - Nukta normalization baked into normalize_for_match() used by best_token_match()

    Returns (best_idx, matched).
    """
    if not fingerprint or from_idx >= len(groq_words):
        return from_idx, False

    stop_at = min(len(groq_words), max(from_idx + 1, stop_at))
    best_score = -1.0
    best_idx = from_idx

    for i in range(from_idx, stop_at):
        score = 0.0
        groq_pos = i
        chain_broken = False

        for token in fingerprint:
            if groq_pos >= len(groq_words):
                chain_broken = True
                break

            if is_digit_token(token):
                # Digit wildcard: consume 1 Groq word unconditionally, no score, no break
                groq_pos += 1
                continue

            sim, tokens_used = best_token_match(groq_words, groq_pos, token)
            if sim >= 0.50:
                score += sim
                groq_pos += tokens_used
            else:
                chain_broken = True
                break

        if not chain_broken and score > best_score:
            best_score = score
            best_idx = i

        if best_score >= len(fingerprint) * 0.85:
            break

    # Count non-digit fingerprint tokens to determine required minimum score
    non_digit_fp = [t for t in fingerprint if not is_digit_token(t)]
    min_required = 1.1 if len(non_digit_fp) >= 2 else 0.5
    matched = best_score >= min_required
    return (best_idx if matched else from_idx), matched


def detect_silence_gaps(words: list, min_gap_s: float = 3.0) -> list[tuple[float, float]]:
    """
    Scan the Groq words list for gaps longer than min_gap_s seconds.
    Returns a list of (gap_end_time, gap_start_of_next_word) tuples.
    """
    gaps = []
    for i in range(len(words) - 1):
        gap = words[i + 1]["start"] - words[i]["end"]
        if gap > min_gap_s:
            gaps.append((float(words[i]["end"]), float(words[i + 1]["start"])))
    return gaps


def align_text_anchored(scenes: list, words: list, duration: float) -> tuple[list, list]:
    """
    Align scenes to Groq word timestamps using text-anchored forward search.
    Enforces a hard limit of >=3 speakable content words per scene.
    Uses a three-tier cursor advance strategy and proportional fallback for unmatched endpoints.
    Detects silence gaps and marks scenes that fall inside them as SILENCE_GAP.
    """
    groq_total = len(words)
    script_total = sum(len(content_words(s.get("text", ""))) for s in scenes)
    groq_ratio = groq_total / max(script_total, 1)
    silence_gaps = detect_silence_gaps(words)

    cursor = 0
    log_entries = []

    for scene in scenes:
        scene_text = scene.get("text", "")
        tokens = content_words(scene_text)
        n = len(tokens)

        if n < 3:
            raise ValueError(
                f"Scene '{scene.get('id')}' has only {n} speakable content words "
                f"(text: '{scene_text}'). Minimum required is 3. "
                f"Please review scenes.json and confirm with user before re-running."
            )

        estimate = max(1, round(n * groq_ratio))

        # START anchor
        fingerprint = tokens[:3]
        anchor_start, start_matched = search_forward(
            words, cursor, fingerprint, stop_at=cursor + 60
        )

        # END anchor
        tail = tokens[-2:]
        anchor_end, end_matched = search_forward(
            words, anchor_start, tail, stop_at=anchor_start + estimate + 20
        )

        # Assign start_time
        scene["start_time"] = round(float(words[anchor_start]["start"]), 3)

        # Assign end_time
        if end_matched:
            last_tail_idx = min(anchor_end + max(0, len(tail) - 1), groq_total - 1)
            fallback_end_idx = last_tail_idx
            scene["end_time"] = round(float(words[last_tail_idx]["end"]), 3)
        else:
            fallback_end_idx = min(anchor_start + estimate, groq_total - 1)
            scene["end_time"] = round(float(words[fallback_end_idx]["end"]), 3)

        # Determine status — check for silence gap after FALLBACK
        status = ("OK" if (start_matched and end_matched)
                  else "START_ONLY" if start_matched
                  else "FALLBACK")

        if status == "FALLBACK":
            cursor_end = words[min(cursor, groq_total - 1)]["end"]
            for gap_end, gap_next_start in silence_gaps:
                if gap_end <= cursor_end <= gap_next_start:
                    status = "SILENCE_GAP"
                    scene["start_time"] = round(gap_end, 3)
                    scene["end_time"] = round(gap_next_start, 3)
                    break

        log_entries.append({
            "scene_id": scene.get("id"),
            "status": status,
            "start_matched": start_matched,
            "end_matched": end_matched,
            "anchor_start_idx": anchor_start,
            "anchor_end_idx": fallback_end_idx,
            "start_time": scene["start_time"],
            "end_time": scene["end_time"],
            "fingerprint": fingerprint,
            "tail": tail,
        })

        # Three-tier cursor advance
        # Phase 1 fix: when end_matched=True on a FALLBACK scene (start missed but
        # end tail was found), advance cursor to the verified tail end, not just
        # anchor_start + estimate//2, which would undershoot and cause overlap.
        if end_matched:
            # Both OK and FALLBACK-with-end: cursor moves past the verified tail end
            cursor = fallback_end_idx + 1
        elif start_matched:
            # START_ONLY: start matched, end estimate
            cursor = anchor_start + estimate
        else:
            # Full FALLBACK: no anchors — advance by half estimate to avoid overshoot
            cursor = anchor_start + max(3, estimate // 2)

        cursor = min(cursor, groq_total - 1)

    # ── Retroactive Anchor Propagation Pass (full chain resolution) ───────────
    # Walk forward. For any scene with end_matched=False, find the nearest
    # subsequent scene with start_matched=True and use its verified start_time
    # as the end boundary. Handles chains of consecutive FALLBACKs.
    for i in range(len(scenes) - 1):
        if log_entries[i]["end_matched"]:
            continue  # end already verified, skip

        # Find the nearest subsequent verified start anchor
        for j in range(i + 1, len(scenes)):
            if log_entries[j]["start_matched"]:
                verified_next_start = scenes[j]["start_time"]
                current_start = scenes[i]["start_time"]
                current_end = scenes[i]["end_time"]

                if verified_next_start > current_end:
                    scenes[i]["end_time"] = verified_next_start
                    log_entries[i]["end_time"] = verified_next_start
                elif verified_next_start < current_end and (verified_next_start - current_start >= 2.0):
                    scenes[i]["end_time"] = verified_next_start
                    log_entries[i]["end_time"] = verified_next_start
                break

    # ── Phase 3: Sandwich Constraint Pass ─────────────────────────────────────
    # For any FALLBACK scene (start not matched), if its immediate predecessor
    # has a verified end_time AND its immediate successor has a verified start_time,
    # pin the FALLBACK scene's boundaries to those two anchors.
    # This eliminates start_time < prev_end_time anomalies (the bug seen in scene-008).
    for i in range(1, len(scenes) - 1):
        if log_entries[i]["start_matched"]:
            continue  # scene has its own anchor, no need to sandwich

        prev_entry = log_entries[i - 1]
        next_entry = log_entries[i + 1]

        # Previous scene must have a verified or propagated end
        prev_end = scenes[i - 1]["end_time"]
        # Next scene must have a verified start anchor
        if not next_entry["start_matched"]:
            continue  # next scene is also unanchored — can't constrain

        next_start = scenes[i + 1]["start_time"]

        # Only apply if the sandwich produces a positive-duration interval
        if next_start > prev_end + 0.05:
            scenes[i]["start_time"] = round(prev_end, 3)
            scenes[i]["end_time"] = round(next_start, 3)
            log_entries[i]["start_time"] = round(prev_end, 3)
    # Shared Post-processing Pass: Character-Weighted Fallback Window Allocation
    from studio.alignment.base import apply_character_weighted_fallback
    scenes, log_entries = apply_character_weighted_fallback(scenes, log_entries, duration)

    return scenes, log_entries


align_scenes = align_text_anchored


def main():
    parser = argparse.ArgumentParser(description="Align Groq timestamps to scenes using text-anchored matching or DP")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory")
    parser.add_argument("--mode", choices=["dp", "anchored"], default="dp", help="Alignment mode: 'dp' (DP Monotonic, default) or 'anchored'")
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    scenes_path = project_dir / "scenes.json"
    timestamps_path = project_dir / "audio" / "timestamps.json"
    log_path = project_dir / "audio" / "alignment_log.json"

    if not scenes_path.exists():
        print(f"ERROR: scenes.json not found at {scenes_path}", file=sys.stderr)
        sys.exit(1)
    if not timestamps_path.exists():
        print(f"ERROR: timestamps.json not found at {timestamps_path}", file=sys.stderr)
        sys.exit(1)

    scenes_data = json.loads(scenes_path.read_text(encoding="utf-8"))
    ts_data = json.loads(timestamps_path.read_text(encoding="utf-8"))

    scenes = scenes_data["scenes"]
    words = ts_data["words"]
    duration = float(ts_data["duration"])
    groq_word_count = len(words)

    script_words = sum(len(content_words(s.get("text", ""))) for s in scenes)
    print(f"→ Aligning {len(scenes)} scenes via {args.mode.upper()} alignment mode")
    print(f"  Script content words: {script_words} | Groq words: {groq_word_count} | Duration: {duration:.2f}s")

    if args.mode == "dp":
        from studio.alignment.dp import align_text_dp
        scenes, log_entries = align_text_dp(scenes, words, duration)
    else:
        scenes, log_entries = align_text_anchored(scenes, words, duration)

    scenes = normalize_scene_intervals(scenes, duration)
    scenes_data["scenes"] = scenes

    # Save scenes.json
    scenes_path.write_text(json.dumps(scenes_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Compute summary stats & save alignment_log.json
    ok_count = sum(1 for entry in log_entries if entry["status"] == "OK")
    start_only_count = sum(1 for entry in log_entries if entry["status"] == "START_ONLY")
    fallback_count = sum(1 for entry in log_entries if entry["status"] == "FALLBACK")
    silence_gap_count = sum(1 for entry in log_entries if entry["status"] == "SILENCE_GAP")

    log_data = {
        "project_name": scenes_data.get("project_name", project_dir.name),
        "groq_words": groq_word_count,
        "script_words": script_words,
        "groq_ratio": round(groq_word_count / max(script_words, 1), 4),
        "scenes_total": len(scenes),
        "scenes_ok": ok_count,
        "scenes_start_only": start_only_count,
        "scenes_fallback": fallback_count,
        "scenes_silence_gap": silence_gap_count,
        "scenes": log_entries
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"✓ scenes.json updated with text-anchored timestamps")
    print(f"✓ Alignment log written to: {log_path}")
    print(f"  Alignment stats -> OK: {ok_count}/{len(scenes)} | START_ONLY: {start_only_count} | FALLBACK: {fallback_count} | SILENCE_GAP: {silence_gap_count}")

    if fallback_count > 0:
        print(f"  ⚠ Warnings logged for {fallback_count} FALLBACK scene(s):", file=sys.stderr)
        for entry in log_entries:
            if entry["status"] == "FALLBACK":
                print(f"    - {entry['scene_id']}: Fingerprint {entry['fingerprint']} not found in transcript", file=sys.stderr)
    if silence_gap_count > 0:
        print(f"  ℹ {silence_gap_count} scene(s) mapped to silence gap (no spoken audio expected)", file=sys.stderr)


if __name__ == "__main__":
    main()
