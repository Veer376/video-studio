# YouTube Publishing Stage

Use this reference as the project-context adapter for the standalone `youtube` skill. Do not use a project-owned publishing wrapper.

## Load the Platform Skill

Invoke the `youtube` skill and read its relevant references before acting:

- `references/auth.md` for identity confirmation
- `references/upload.md` for upload
- `references/data.md` for status or attaching an existing upload
- `references/media.md` for thumbnail compression

Follow all `youtube` hard rules. In particular, require an explicit channel alias, run `whoami` before every upload, and default visibility to `private`.

## Project Inputs

Resolve these project artifacts:

```text
video       = library/<project_name>/output/final-video.mp4
metadata    = library/<project_name>/youtube/metadata.json
thumbnails  = library/<project_name>/youtube/thumbnails/*.{png,jpg,jpeg}
upload      = library/<project_name>/youtube/upload.json
```

Require the video and `metadata.json`. Read:

- title from `recommended_title`, falling back to `title`
- description from `description`
- optional tags from `tags`
- optional category from `category_id` or `categoryId`, defaulting to `22`
- optional audience flag from `selfDeclaredMadeForKids`, defaulting to false

Ask the user which generated thumbnail to use when more than one exists. Do not silently choose `thumbnail-01`. An upload without a thumbnail requires explicit confirmation.

## Upload

1. Ask for the registered channel alias if it is not already explicit.
2. Run the `youtube` skill's channel listing if the alias is uncertain.
3. Run its `auth.py whoami --channel <channel_alias>` and show the confirmed channel identity.
4. If visibility is unspecified, use `private`; require explicit user instruction for `public`.
5. Run the `youtube` skill's `upload.py` directly with the resolved video, title, description, selected thumbnail, tags, category, audience flag, visibility, and `--json`.
6. Treat the upload as successful only when the command returns a video ID. Report thumbnail failure separately; upload success does not prove the thumbnail was set.
7. Save the returned JSON payload to `library/<project_name>/youtube/upload.json`, adding `project`, `metadata_path`, and the selected thumbnail path when absent.

Do not re-upload when `upload.json` already contains a video ID unless the user explicitly requests a replacement upload.

## Status

Read `video_id` from `upload.json`, then use the `youtube` skill's `data.py fetch` directly with:

```text
--channel <channel_alias> --processing-details --json
```

Report privacy, upload status, and processing status from the returned data. Update `upload.json` with the latest status fields and check time; preserve the original upload payload.

## Attach an Existing YouTube Upload

For a video uploaded manually in YouTube Studio:

1. Require the channel alias and video ID or URL.
2. Confirm identity with the `youtube` skill's `whoami` command.
3. Fetch the video through the `youtube` skill using the explicit channel alias.
4. Confirm that the fetched video belongs to the intended authenticated channel before associating it.
5. Write or update `upload.json` with the video ID, URL, project path, fetched status, and attachment time.
6. Refuse to replace a different existing video ID without explicit confirmation.

## Thumbnail Compression

Use the `youtube` skill's `media.py compress-thumbnail` directly. Keep any derived compressed file under the project's `youtube/thumbnails/` folder, then record the actual uploaded thumbnail path in `upload.json`.

## Write Boundary

Write only:

```text
library/<project_name>/youtube/upload.json
library/<project_name>/youtube/thumbnails/<derived-compressed-file>
```

Do not create `upload.md` or duplicate YouTube API scripts inside this skill.
