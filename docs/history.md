# Development history

This repository joins two independently developed source histories with an explicit merge:

| Original project | Main-branch development commits | Earliest author date |
| --- | ---: | --- |
| Image studio | 158 | 31 July 2026 |
| Video studio | 38 | 10 August 2026 |

All 196 development commit records were retained. Generated media, private production files, channel research, and scratch content were removed from both histories before consolidation. This changes affected commit IDs. Author/committer identities, dates, messages, and mapped parent relationships were verified against private original-history backups. Media-only records may now have empty trees; they were retained rather than inventing a different development sequence.

Each cleaned tree was moved under its pipeline in a relocation commit, then merged without squashing or linearizing either ancestry. The current production work and release setup are subsequent commits. Saved stashes are preserved in private backups, not counted as additional development commits.

Exact original Git bundles, working-file snapshots, old-to-new commit maps, cleanup manifests, and verification reports are retained privately. They are not public refs or release assets. The original project folders were not reset or rewritten during preparation.
