# Scripts

This directory contains durable, reusable project pipeline and media utilities. Every script must remain useful beyond the task that introduced it.

## Standards

1. **Executable & Shebang**:
   - Begin every script with `#!/usr/bin/env python3`.
   - Ensure files have executable permissions (`chmod +x`).

2. **Story-Agnostic Design**:
   - Never hardcode story paths, scene IDs, or story-specific assets.
   - Expose configurable parameters via CLI arguments (e.g. `--config`, `--story`, `--input`, `--output`).

3. **Standard CLI Interface**:
   - Use `argparse` with clear `--help` descriptions and sensible defaults.
   - Use `Path(__file__).resolve().parent.parent` for workspace-relative path resolution so scripts run reliably from any working directory.

4. **Directory Ownership**:
   - `scripts/`: Backend pipeline tools, video processing, and media automation utilities.
   - `app/`: Interactive Terminal UI (TUI) and desktop GUI applications.
   - `scratch/` & `temp/`: Ad-hoc experiments, scraping tests, and transient artifacts.
