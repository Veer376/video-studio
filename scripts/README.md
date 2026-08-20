# Scripts

This directory contains durable project utilities. Every script must remain useful beyond the task that introduced it.

## Standard

- Give each script one clear responsibility and a stable, descriptive name.
- Begin each script with a short module docstring stating what it does, its primary inputs, and what it produces or changes.
- For command-line scripts, expose the required inputs as arguments and provide useful `--help` text.
- Reuse shared modules where appropriate; individuality does not require duplicated logic.
- Keep experiments, diagnostics, generated files, and one-time workarounds outside this directory. Promote them here only when they become maintained project utilities.
