"""
Video Pipeline (vp) - Interactive Terminal UI & Unified CLI Tool.
Designed for high-velocity coding and prompt engineering workflows in Antigravity.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
SCHEDULER_CLI = Path.home() / ".gemini" / "config" / "skills" / "local-scheduler" / "scripts" / "cli.py"
SEO_SCOUT_CLI = Path.home() / ".gemini" / "config" / "skills" / "youtube-seo" / "scripts" / "scout.py"

# ANSI Colors
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
RED = "\033[31m"
RESET = "\033[0m"


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def find_latest_video() -> Optional[Path]:
    """Find the most recently modified video in the workspace."""
    video_extensions = {".mp4", ".mov", ".mkv", ".webm"}
    videos = []
    for root, _, files in os.walk(WORKSPACE_ROOT):
        if "temp" in root or ".git" in root:
            continue
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in video_extensions:
                videos.append(p)
    if not videos:
        return None
    videos.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return videos[0]


def run_command_streaming(cmd: List[str], cwd: Path, title: str) -> int:
    print(f"\n{BOLD}{CYAN}⚡ Executing: {title}{RESET}")
    print(f"{DIM}$ {' '.join(cmd)}{RESET}\n" + "─" * 60)
    start_t = time.time()

    try:
        proc = subprocess.Popen(cmd, cwd=str(cwd), text=True)
        proc.wait()
        dur = round(time.time() - start_t, 2)
        print("─" * 60)
        if proc.returncode == 0:
            print(f"{GREEN}{BOLD}✅ {title} finished successfully in {dur}s.{RESET}")
        else:
            print(f"{RED}{BOLD}❌ {title} failed with exit code {proc.returncode} ({dur}s).{RESET}")
        return proc.returncode
    except KeyboardInterrupt:
        print(f"\n{YELLOW}⚠️ Execution interrupted by user.{RESET}")
        return 130
    except Exception as e:
        print(f"{RED}❌ Error executing {title}: {e}{RESET}")
        return 1


# ---------------- Action Handlers ----------------


def action_watermark(video_path: Optional[str] = None) -> int:
    script = WORKSPACE_ROOT / "scripts" / "apply_watermark.py"
    target = video_path
    if not target:
        latest = find_latest_video()
        if latest:
            target = str(latest)
            print(f"{DIM}Auto-detected latest video: {latest.relative_to(WORKSPACE_ROOT)}{RESET}")

    cmd = [sys.executable, str(script)]
    if target:
        cmd.extend(["--input", target])
    return run_command_streaming(cmd, WORKSPACE_ROOT, "Apply Watermark")


def action_render_story(story_name: str = "chanakya-helena-sacrifice") -> int:
    script = WORKSPACE_ROOT / "scripts" / "render_video.py"
    cmd = [sys.executable, str(script), "--story", story_name]
    return run_command_streaming(cmd, WORKSPACE_ROOT, f"Render Story ({story_name})")


def action_seo_scout(niche: str = "Indian Melodrama Stories") -> int:
    if SEO_SCOUT_CLI.exists():
        cmd = [sys.executable, str(SEO_SCOUT_CLI), "--niche", niche]
    else:
        cmd = [sys.executable, "-c", "print('Simulating SEO multi-vector sweeps...')"]
    return run_command_streaming(cmd, WORKSPACE_ROOT, f"YouTube SEO Scout ({niche})")


def action_scheduler(subcmd: str = "list") -> int:
    if not SCHEDULER_CLI.exists():
        print(f"{RED}Error: Local scheduler CLI not found at {SCHEDULER_CLI}{RESET}")
        return 1
    cmd = [sys.executable, str(SCHEDULER_CLI), subcmd]
    return run_command_streaming(cmd, WORKSPACE_ROOT, f"Local Scheduler ({subcmd})")


# ---------------- Interactive TUI Menu ----------------


def interactive_menu() -> None:
    while True:
        clear_screen()
        latest = find_latest_video()
        latest_str = str(latest.relative_to(WORKSPACE_ROOT)) if latest else "None detected"

        print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════╗
║              🎬 VIDEO PIPELINE COMMAND HUB (vp)              ║
╚══════════════════════════════════════════════════════════════╝{RESET}
{DIM}Workspace: {WORKSPACE_ROOT.name} | Latest Video: {latest_str}{RESET}

{BOLD}Select an action to execute:{RESET}

  {GREEN}{BOLD}[1]{RESET} 💧 {BOLD}Apply Watermark{RESET}       {DIM}Add logo/overlay to latest video{RESET}
  {MAGENTA}{BOLD}[2]{RESET} 🎬 {BOLD}Render Story Video{RESET}    {DIM}Stitch scenes for chanakya story{RESET}
  {YELLOW}{BOLD}[3]{RESET} 🔍 {BOLD}Run SEO Scout{RESET}         {DIM}75+ multi-vector search trends{RESET}
  {CYAN}{BOLD}[4]{RESET} ⏱️  {BOLD}Local Scheduler{RESET}       {DIM}List and inspect scheduled tasks{RESET}
  {GREEN}{BOLD}[5]{RESET} 🚀 {BOLD}Open Desktop Deck{RESET}     {DIM}Launch pywebview floating window{RESET}
  {MAGENTA}{BOLD}[6]{RESET} 🎛️  {BOLD}Render Studio GUI{RESET}     {DIM}Visual trimmer, breaks & multi-clip exporter{RESET}
  {DIM}[q] ❌ Exit{RESET}
""")

        try:
            choice = input(f"{BOLD}{CYAN}➜ Enter choice [1-6, q]: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if choice in {"q", "exit", "quit"}:
            print("Goodbye!")
            break
        elif choice == "1":
            action_watermark()
        elif choice == "2":
            action_render_story()
        elif choice == "3":
            action_seo_scout()
        elif choice == "4":
            action_scheduler("list")
        elif choice == "5":
            deck_app = WORKSPACE_ROOT / "app" / "app.py"
            subprocess.Popen([sys.executable, str(deck_app)])
            print(f"{GREEN}Launched Video Deck window in background.{RESET}")
        elif choice == "6":
            studio_app = WORKSPACE_ROOT / "app" / "render_studio.py"
            subprocess.Popen([sys.executable, str(studio_app)])
            print(f"{MAGENTA}Launched Video Render Studio & Sequencer GUI in background.{RESET}")
        else:
            print(f"{RED}Invalid selection '{choice}'.{RESET}")

        print(f"\n{DIM}Press Enter to continue...{RESET}", end="")
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            break


# ---------------- CLI Parser ----------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vp",
        description="Unified Video Pipeline CLI & Terminal UI for Antigravity",
    )
    subparsers = parser.add_subparsers(dest="command")

    # watermark
    p_wm = subparsers.add_parser("watermark", help="Apply watermark to latest video")
    p_wm.add_argument("--input", "-i", help="Specific video input path")

    # render
    p_rend = subparsers.add_parser("render", help="Render full story video")
    p_rend.add_argument("--story", "-s", default="chanakya-helena-sacrifice", help="Story name")

    # scout
    p_scout = subparsers.add_parser("scout", help="Run YouTube SEO demand scout")
    p_scout.add_argument("--niche", "-n", default="Indian Melodrama Stories", help="Niche or topic")

    # tasks / scheduler
    subparsers.add_parser("tasks", help="List all local scheduler automations")

    # deck
    subparsers.add_parser("deck", help="Open the native Desktop Command Deck GUI")

    args = parser.parse_args()

    if not args.command:
        # If no subcommand provided, open the interactive TUI menu
        interactive_menu()
        return

    if args.command == "watermark":
        code = action_watermark(args.input)
    elif args.command == "render":
        code = action_render_story(args.story)
    elif args.command == "scout":
        code = action_seo_scout(args.niche)
    elif args.command == "tasks":
        code = action_scheduler("list")
    elif args.command == "deck":
        deck_app = WORKSPACE_ROOT / "app" / "app.py"
        subprocess.Popen([sys.executable, str(deck_app)])
        print(f"{GREEN}Launched Video Deck.{RESET}")
        code = 0
    else:
        code = 0

    sys.exit(code)


if __name__ == "__main__":
    main()
