"""
Align Groq word timestamps to scenes using Anchor-Constrained Monotonic Dynamic Programming.
Updates scenes.json in-place with start_time and end_time per scene,
and writes an alignment_log.json in the audio/ directory for inspection.

Usage:
    python3 -m studio.alignment.dp --project-dir library/2026-08-01_krishna-motivation
"""
import argparse
import json
import math
import sys
from pathlib import Path

from studio.alignment.base import (
    AlignmentEngine,
    bigram_similarity,
    content_words,
    normalize_for_match,
    normalize_scene_intervals,
)


def calculate_sequence_similarity(scene_tokens: list[str], groq_tokens: list[str]) -> float:
    """Calculate overall text similarity between scene content words and candidate Groq words."""
    if not scene_tokens or not groq_tokens:
        return 0.0
    norm_scene = [normalize_for_match(t) for t in scene_tokens if t.strip()]
    norm_groq = [normalize_for_match(t) for t in groq_tokens if t.strip()]
    if not norm_scene or not norm_groq:
        return 0.0

    matches = 0
    g_idx = 0
    for s_word in norm_scene:
        best_sim = 0.0
        best_j = g_idx
        for j in range(max(0, g_idx - 2), min(len(norm_groq), g_idx + 5)):
            sim = bigram_similarity(s_word, norm_groq[j])
            if sim > best_sim:
                best_sim = sim
                best_j = j
        if best_sim >= 0.5:
            matches += best_sim
            g_idx = max(g_idx, best_j + 1)

    return matches / max(len(norm_scene), 1)


def generate_candidates(scenes: list, groq_words: list) -> list[list[dict]]:
    """
    Generate candidate spans [start_idx, end_idx] for each scene across groq_words.
    """
    groq_total = len(groq_words)
    script_total = sum(len(content_words(s.get("text", ""))) for s in scenes)
    groq_ratio = groq_total / max(script_total, 1)

    all_candidates = []
    expected_start_idx = 0.0

    for idx, scene in enumerate(scenes):
        tokens = content_words(scene.get("text", ""))
        n_words = len(tokens)
        expected_len = max(3, round(n_words * groq_ratio))

        candidates = []
        search_min = max(0, int(expected_start_idx) - 40)
        search_max = min(groq_total - 1, int(expected_start_idx) + 80)

        for s_idx in range(search_min, search_max):
            for length in [expected_len - 5, expected_len - 2, expected_len, expected_len + 2, expected_len + 5]:
                if length < 3:
                    continue
                e_idx = s_idx + length - 1
                if e_idx >= groq_total:
                    continue

                span_groq_words = [groq_words[k].get("word", "") for k in range(s_idx, e_idx + 1)]
                text_sim = calculate_sequence_similarity(tokens, span_groq_words)

                fp_sim = 0.0
                if tokens and len(tokens) >= 3:
                    fp = tokens[:3]
                    first_3 = span_groq_words[:3]
                    fp_sim = calculate_sequence_similarity(fp, first_3)

                tail_sim = 0.0
                if tokens and len(tokens) >= 2:
                    tail = tokens[-2:]
                    last_2 = span_groq_words[-2:]
                    tail_sim = calculate_sequence_similarity(tail, last_2)

                score = (0.50 * text_sim) + (0.30 * fp_sim) + (0.20 * tail_sim)

                candidates.append({
                    "start_idx": s_idx,
                    "end_idx": e_idx,
                    "score": score,
                    "start_time": float(groq_words[s_idx]["start"]),
                    "end_time": float(groq_words[e_idx]["end"]),
                    "fp_sim": fp_sim,
                    "tail_sim": tail_sim,
                    "fp": tokens[:3] if len(tokens) >= 3 else tokens,
                    "tail": tokens[-2:] if len(tokens) >= 2 else tokens
                })

        candidates.sort(key=lambda c: c["score"], reverse=True)
        top_candidates = candidates[:10]

        # Always include proportional fallback candidate
        p_start = min(int(expected_start_idx), groq_total - 1)
        p_end = min(p_start + expected_len - 1, groq_total - 1)
        top_candidates.append({
            "start_idx": p_start,
            "end_idx": p_end,
            "score": 0.1,
            "start_time": float(groq_words[p_start]["start"]),
            "end_time": float(groq_words[p_end]["end"]),
            "fp_sim": 0.0,
            "tail_sim": 0.0,
            "fp": tokens[:3] if len(tokens) >= 3 else tokens,
            "tail": tokens[-2:] if len(tokens) >= 2 else tokens
        })

        all_candidates.append(top_candidates)
        expected_start_idx += expected_len

    return all_candidates


def run_dp_alignment(scenes: list, all_candidates: list[list[dict]], groq_words: list) -> tuple[list[dict], float]:
    """
    Run Viterbi Dynamic Programming over candidate spans to select optimal monotonic sequence.
    """
    num_scenes = len(scenes)
    dp = []

    scene0_dp = []
    for c_idx, cand in enumerate(all_candidates[0]):
        dist_pen = 0.05 * cand["start_idx"]
        scene0_dp.append((cand["score"] - dist_pen, -1))
    dp.append(scene0_dp)

    for s_idx in range(1, num_scenes):
        scene_dp = []
        curr_cands = all_candidates[s_idx]
        prev_cands = all_candidates[s_idx - 1]
        prev_dp = dp[s_idx - 1]

        for c_idx, curr_c in enumerate(curr_cands):
            best_prev_score = -1e9
            best_prev_idx = -1

            for p_idx, prev_c in enumerate(prev_cands):
                prev_cum_score, _ = prev_dp[p_idx]

                if curr_c["start_idx"] < prev_c["start_idx"]:
                    continue

                overlap = max(0, prev_c["end_idx"] - curr_c["start_idx"] + 1)
                overlap_pen = 0.2 * overlap

                gap = max(0, curr_c["start_idx"] - prev_c["end_idx"] - 1)
                gap_pen = 0.02 * gap if gap > 10 else 0.0

                total_score = prev_cum_score + curr_c["score"] - overlap_pen - gap_pen

                if total_score > best_prev_score:
                    best_prev_score = total_score
                    best_prev_idx = p_idx

            scene_dp.append((best_prev_score, best_prev_idx))
        dp.append(scene_dp)

    best_last_score = -1e9
    best_last_cand = 0
    for c_idx, (score, _) in enumerate(dp[-1]):
        if score > best_last_score:
            best_last_score = score
            best_last_cand = c_idx

    chosen_path = []
    curr_cand = best_last_cand
    for s_idx in range(num_scenes - 1, -1, -1):
        cand = all_candidates[s_idx][curr_cand]
        chosen_path.append((s_idx, cand))
        _, parent = dp[s_idx][curr_cand]
        curr_cand = parent

    chosen_path.reverse()
    return chosen_path, best_last_score


def align_text_dp(scenes: list, words: list, duration: float) -> tuple[list, list]:
    """
    Main entry point for DP Monotonic Scene Alignment.
    """
    all_candidates = generate_candidates(scenes, words)
    chosen_path, _ = run_dp_alignment(scenes, all_candidates, words)

    log_entries = []
    for scene_idx, cand in chosen_path:
        scene = scenes[scene_idx]
        st = round(cand["start_time"], 3)
        et = round(cand["end_time"], 3)
        scene["start_time"] = st
        scene["end_time"] = et

        fp_sim = cand["fp_sim"]
        score = cand["score"]
        status = "OK" if fp_sim >= 0.5 or score >= 0.4 else "FALLBACK"

        log_entries.append({
            "scene_id": scene.get("id"),
            "status": status,
            "start_matched": (fp_sim >= 0.5),
            "end_matched": (cand["tail_sim"] >= 0.5),
            "anchor_start_idx": cand["start_idx"],
            "anchor_end_idx": cand["end_idx"],
            "start_time": st,
            "end_time": et,
            "fingerprint": cand["fp"],
            "tail": cand["tail"]
        })

    # Shared Post-processing Pass: Character-Weighted Fallback Window Allocation
    from studio.alignment.base import apply_character_weighted_fallback
    scenes, log_entries = apply_character_weighted_fallback(scenes, log_entries, duration)

    return scenes, log_entries


align_scenes = align_text_dp


def main():
    parser = argparse.ArgumentParser(description="Align Groq timestamps to scenes using DP Monotonic Alignment")
    parser.add_argument("--project-dir", required=True, help="Path to project directory")
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    scenes_path = project_dir / "scenes.json"
    timestamps_path = project_dir / "audio" / "timestamps.json"
    log_path = project_dir / "audio" / "alignment_log.json"

    if not scenes_path.exists() or not timestamps_path.exists():
        print(f"ERROR: Missing scenes.json or timestamps.json in {project_dir}", file=sys.stderr)
        sys.exit(1)

    scenes_data = json.loads(scenes_path.read_text(encoding="utf-8"))
    ts_data = json.loads(timestamps_path.read_text(encoding="utf-8"))

    scenes = scenes_data["scenes"]
    words = ts_data["words"]
    duration = float(ts_data["duration"])

    print(f"→ Aligning {len(scenes)} scenes via DP Monotonic Scene Alignment")
    scenes, log_entries = align_text_dp(scenes, words, duration)
    scenes = normalize_scene_intervals(scenes, duration)
    scenes_data["scenes"] = scenes

    scenes_path.write_text(json.dumps(scenes_data, indent=2, ensure_ascii=False), encoding="utf-8")

    ok_count = sum(1 for e in log_entries if e["status"] == "OK")
    fallback_count = sum(1 for e in log_entries if e["status"] == "FALLBACK")

    log_data = {
        "project_slug": scenes_data.get("project_slug", project_dir.name),
        "groq_words": len(words),
        "alignment_mode": "dp_monotonic",
        "scenes_total": len(scenes),
        "scenes_ok": ok_count,
        "scenes_fallback": fallback_count,
        "scenes": log_entries
    }
    log_path.write_text(json.dumps(log_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"✓ scenes.json updated with DP timestamps")
    print(f"✓ Alignment log written to: {log_path}")
    print(f"  Alignment stats -> OK: {ok_count}/{len(scenes)} | FALLBACK: {fallback_count}")


if __name__ == "__main__":
    main()
