# Recovery

Run commands from the owning pipeline directory. Back up a production root before editing runtime records or replacing media.

## Image story

```bash
uv run --locked produce-visuals plan work/my-story
uv run --locked produce-visuals status work/my-story
uv run --locked produce-visuals run work/my-story --images-only --dry-run
uv run --locked produce-visuals run work/my-story --images-only --scene scene-001
```

The last command can call a provider. A rerun reuses an asset only when the saved fingerprint, ordered references, output path/hash, and verified media still match. Prompt/style/provider/model/reference changes invalidate affected assets. Continuations depend on their predecessor; cross-scene references use the referenced scene's terminal still.

After inspecting a recurring continuity anchor, record approval:

```bash
uv run --locked produce-visuals anchor work/my-story --asset scene-001:primary --subject subject-id
```

Use a declared subject/location ID from `continuity.json`; replacing its anchor bytes invalidates approval. `anchor --help` lists location approval as an alternative.

A submitted Flow job/idempotency key is durable: rerun to poll/replay the same request, rather than deleting state and buying another generation. Google failures after the submission boundary become `uncertain`; automatic repetition is disabled. Check remote/provider evidence before explicitly permitting retry:

```bash
uv run --locked produce-visuals retry work/my-story --asset scene-001:primary
```

Retry is intentionally refused for durable Flow submission state. Do not delete manifests, lock files, or job state to bypass protection. The filesystem writer lock is released when its owning process exits; the lock filename alone does not indicate an active writer.

Narration steps are separate:

```bash
uv run --locked story-video voice-step narrate work/my-story
uv run --locked story-video voice-step transcribe work/my-story --unit unit-001
uv run --locked story-video voice-step align work/my-story
```

`--force` on a voice step may regenerate/retranscribe and incur charges; alignment is local. Voice generation reuses per-unit audio based on its input hash. Existing audio without an older manifest can be reused for compatibility, so inspect it when importing legacy work. After changing upstream narration/timing/media, use `render-story --force` to rebuild renderer caches. The final MP4 is a derived output, not the only backup.

## Generated video

New generation waits when an active video needs review. Inspect video/audio, create the contact sheet, and update the pending record as described in the pipeline README. Final rendering verifies the active hash; copying another clip over it invalidates the review.

For a diagnosed rejected clip, keep its `needs_fix` findings and use one replacement:

```bash
uv run --locked python -m scripts.generate_scenes --config work/my-story/scenes.json --scene s001 --regenerate
```

This can call a paid provider. The reviewed active file/evidence are archived as `-a1` or `-a2`; two generations are the configured limit. If another replacement remains unusable, stop and revise the creative decision instead of removing attempt state.

Restore an archived clip only when no active clip occupies the destination:

```bash
uv run --locked python -m scripts.generate_scenes --config work/my-story/scenes.json --scene s001 --restore a1
```

Restoration is local and returns the active clip to `pending_review`. Inspect and accept it again before rendering. Back up the whole production root to preserve archived clips, contact sheets, reviews, and current selection together.
