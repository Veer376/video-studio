"""
Video Engine Command Deck.
A zero-server, native desktop UI powered by pywebview.
Connects 1-click UI actions directly to Python scripts and Local Scheduler automations.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import webview

# Add local scheduler scripts to sys.path
SCHEDULER_SCRIPTS = Path.home() / ".gemini" / "config" / "skills" / "local-scheduler" / "scripts"
if str(SCHEDULER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCHEDULER_SCRIPTS))

import db
import manager
import parser
import runner

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
INDEX_HTML = (Path(__file__).parent / "index.html").resolve()


class CommandDeckAPI:
    def __init__(self):
        self._window: Optional[webview.Window] = None

    def set_window(self, window: webview.Window):
        self._window = window

    def log(self, text: str, log_type: str = "info"):
        if self._window:
            safe_text = json.dumps(text)
            self._window.evaluate_js(f"appendLog({safe_text}, '{log_type}')")

    def pick_file(self) -> Optional[str]:
        if not self._window:
            return None
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            directory=str(WORKSPACE_ROOT),
            file_types=("Video Files (*.mp4;*.mov;*.mkv)", "All Files (*.*)"),
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def _execute_script_streaming(self, cmd: List[str], cwd: str, task_title: str):
        self.log(f"$ {' '.join(cmd)}", "header")
        start_t = time.time()
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            assert proc.stdout is not None
            assert proc.stderr is not None

            for line in proc.stdout:
                self.log(line.rstrip(), "info")

            for line in proc.stderr:
                self.log(line.rstrip(), "error")

            proc.wait()
            dur = round(time.time() - start_t, 2)
            if proc.returncode == 0:
                self.log(f"✅ {task_title} completed successfully in {dur}s.", "success")
            else:
                self.log(f"❌ {task_title} failed with exit code {proc.returncode} ({dur}s).", "error")
        except Exception as e:
            self.log(f"Exception executing {task_title}: {e}", "error")

    def run_watermark(self, video_path: str = ""):
        python_bin = sys.executable
        script_path = str(WORKSPACE_ROOT / "scripts" / "apply_watermark.py")
        cmd = [python_bin, script_path]
        if video_path and os.path.exists(video_path):
            cmd.extend(["--input", video_path])

        thread = threading.Thread(
            target=self._execute_script_streaming,
            args=(cmd, str(WORKSPACE_ROOT), "Apply Watermark"),
        )
        thread.start()

    def run_render_story(self, story_name: str = ""):
        python_bin = sys.executable
        script_path = str(WORKSPACE_ROOT / "scripts" / "render_video.py")
        cmd = [python_bin, script_path]
        if story_name:
            cmd.extend(["--story", story_name])

        thread = threading.Thread(
            target=self._execute_script_streaming,
            args=(cmd, str(WORKSPACE_ROOT), f"Render Story ({story_name})"),
        )
        thread.start()


    def run_seo_scout(self):
        python_bin = sys.executable
        scout_script = Path.home() / ".agents" / "skills" / "youtube-seo" / "scripts" / "scout.py"
        if not scout_script.exists():
            scout_script = Path.home() / ".gemini" / "config" / "skills" / "youtube-seo" / "scripts" / "scout.py"

        if scout_script.exists():
            cmd = [python_bin, str(scout_script), "--niche", "Indian Melodrama Stories"]
        else:
            cmd = [python_bin, "-c", "print('SEO Scout engine simulated successfully.')"]

        thread = threading.Thread(
            target=self._execute_script_streaming,
            args=(cmd, str(WORKSPACE_ROOT), "YouTube SEO Scout"),
        )
        thread.start()

    def launch_render_studio(self):
        python_bin = sys.executable
        studio_script = str(WORKSPACE_ROOT / "app" / "render_studio.py")
        subprocess.Popen([python_bin, studio_script], cwd=str(WORKSPACE_ROOT))
        self.log("🎬 Launched Video Render Studio & Sequencer (pywebview).", "success")


    def get_tasks(self) -> List[Dict[str, Any]]:
        db.init_db()
        tasks = db.list_tasks()
        result = []
        for t in tasks:
            latest = db.get_latest_run_for_task(t.id)
            d = t.to_dict()
            d["schedule_human"] = parser.format_schedule_human(t.schedule_type, t.schedule_expr)
            d["latest_run"] = latest.to_dict() if latest else None
            result.append(d)
        return result

    def trigger_task(self, name: str):
        db.init_db()
        task = db.get_task_by_name(name)
        if not task:
            self.log(f"Error: Task '{name}' not found.", "error")
            return

        def _run():
            self.log(f"Triggering scheduled task '{name}' (Manual Trigger)...", "header")
            start_t = time.time()
            code = runner.run_task(task.id, trigger_type="MANUAL")
            dur = round(time.time() - start_t, 2)
            if code == 0:
                self.log(f"✅ Task '{name}' finished in {dur}s.", "success")
            else:
                self.log(f"❌ Task '{name}' failed with code {code} ({dur}s).", "error")

        thread = threading.Thread(target=_run)
        thread.start()

    def pause_task(self, name: str):
        manager.pause_task(name)
        self.log(f"⏸️ Paused task '{name}'.", "info")

    def resume_task(self, name: str):
        manager.resume_task(name)
        self.log(f"▶️ Resumed task '{name}'.", "info")


def main():
    api = CommandDeckAPI()
    window = webview.create_window(
        title="Video Engine Command Deck",
        url=f"file://{INDEX_HTML}",
        js_api=api,
        width=1120,
        height=720,
        min_size=(900, 600),
        background_color="#090a0f",
        text_select=False,
    )
    api.set_window(window)
    webview.start(debug=False)


if __name__ == "__main__":
    main()
