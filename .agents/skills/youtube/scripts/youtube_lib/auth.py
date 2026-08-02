from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import MANAGE_SCOPE, READONLY_SCOPE, UPLOAD_SCOPE, die, load_google_libs


def token_path(scope_profile: str) -> Path:
    config_dir = Path.home() / ".config" / "projects"
    if scope_profile == "upload":
        legacy = config_dir / "youtube_token.json"
        if legacy.exists():
            return legacy
        return config_dir / "youtube_token_upload.json"
    if scope_profile == "manage":
        return config_dir / "youtube_token_manage.json"
    if scope_profile == "readonly":
        return config_dir / "youtube_token_readonly.json"
    die(f"unknown scope profile: {scope_profile}")


def token_candidates(scope_profile: str) -> list[Path]:
    config_dir = Path.home() / ".config" / "projects"
    if scope_profile == "upload":
        return [config_dir / "youtube_token.json", config_dir / "youtube_token_upload.json"]
    if scope_profile == "manage":
        return [config_dir / "youtube_token_manage.json"]
    if scope_profile == "readonly":
        return [config_dir / "youtube_token_readonly.json"]
    die(f"unknown scope profile: {scope_profile}")


def scopes_for_profile(scope_profile: str) -> list[str]:
    if scope_profile == "upload":
        return [UPLOAD_SCOPE]
    if scope_profile == "manage":
        return [MANAGE_SCOPE]
    if scope_profile == "readonly":
        return [READONLY_SCOPE]
    die(f"unknown scope profile: {scope_profile}")


def reset_tokens(scope_profiles: list[str]) -> list[Path]:
    removed: list[Path] = []
    for scope_profile in scope_profiles:
        for token in token_candidates(scope_profile):
            if token.exists():
                token.unlink()
                removed.append(token)
    return removed


def get_credentials(scope_profile: str):
    Request, Credentials, InstalledAppFlow, *_ = load_google_libs()
    config_dir = Path.home() / ".config" / "projects"
    client_secret = config_dir / "youtube_client_secret.json"
    if not client_secret.exists():
        die(f"missing OAuth client secret: {client_secret}")

    scopes = scopes_for_profile(scope_profile)
    token = token_path(scope_profile)

    creds = None
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), scopes)
            creds = flow.run_local_server(port=0, open_browser=True, prompt="consent")
        token.parent.mkdir(parents=True, exist_ok=True)
        token.write_text(creds.to_json(), encoding="utf-8")
    return creds


def youtube_client(scope_profile: str):
    *_, build, _, _ = load_google_libs()
    return build("youtube", "v3", credentials=get_credentials(scope_profile))


def authenticated_channel(youtube) -> dict[str, Any]:
    response = youtube.channels().list(part="id,snippet,contentDetails,status", mine=True).execute()
    channels = response.get("items", [])
    if not channels:
        die("no authenticated YouTube channel found")
    return channels[0]


def print_channel(channel: dict[str, Any]) -> None:
    snippet = channel.get("snippet", {})
    status = channel.get("status", {})
    print(f"channel_id {channel.get('id')}")
    print(f"title {snippet.get('title')}")
    if snippet.get("customUrl"):
        print(f"custom_url {snippet.get('customUrl')}")
    if status.get("privacyStatus"):
        print(f"privacy {status.get('privacyStatus')}")
