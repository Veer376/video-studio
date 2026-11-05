"""Core registry loaders and prompt compilation for video generation."""

from __future__ import annotations

import abc
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HANDLE_PATTERN = re.compile(r"(?<![A-Za-z0-9_])@[A-Za-z][A-Za-z0-9_-]*")
NARRATION_HANDLE_PREFIX = "@narration-"
LOCATION_HANDLE_PREFIX = "@location-"


class VideoError(RuntimeError):
    """Base exception for video generation failures."""


class ConfigError(ValueError):
    """Raised when project or scene configuration cannot be compiled safely."""


class ProviderUnavailableError(VideoError):
    """Raised when a video generation provider is unreachable or unconfigured."""


class CreditError(VideoError):
    """Raised when an account lacks sufficient credits for generation."""


@dataclass(frozen=True)
class CharacterEntry:
    handle: str
    name: str
    reference_path: str
    resolved_reference_path: Path
    profile: str = ""
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LocationEntry:
    handle: str
    name: str
    reference_path: str
    resolved_reference_path: Path
    profile: str = ""
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def load_voices(project_root: Path = PROJECT_ROOT) -> dict[str, str]:
    """Load optional project-level off-screen narration voice profiles."""
    path = project_root / "voices.json"
    if not path.is_file():
        return {}

    data = load_json(path)
    entries = data.get("voices")
    if entries is None:
        return {}
    if not isinstance(entries, list):
        raise ConfigError(f"{path} must contain a voices array")

    voices: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ConfigError(f"Every voice in {path} must be an object")
        handle = entry.get("handle")
        profile = entry.get("profile")
        if (
            not isinstance(handle, str)
            or not HANDLE_PATTERN.fullmatch(handle)
            or not handle.startswith(NARRATION_HANDLE_PREFIX)
        ):
            raise ConfigError(
                f"Invalid narration handle: {handle!r} in {path}; "
                f"expected {NARRATION_HANDLE_PREFIX}<identity>"
            )
        if not isinstance(profile, str) or not profile.strip():
            raise ConfigError(f"Narration voice {handle} in {path} has no profile")
        if handle in voices:
            raise ConfigError(f"Duplicate narration handle: {handle} in {path}")
        voices[handle] = profile.strip()
    return voices


@dataclass(frozen=True)
class CompiledScene:
    prompt: str
    images: list[Path]
    task: str
    handle_order: list[str]
    raw_prompt: str = ""
    annotated_prompt: str = ""
    flow_prompt: str = ""


def resolve_path(project_root: Path, configured_path: str | Path) -> Path:
    path = Path(configured_path)
    return path if path.is_absolute() else project_root / path


def resolve_characters_path(config_path: Path, characters_file: str | Path, project_root: Path = PROJECT_ROOT) -> Path:
    """Resolve character file path whether specified as project-relative or story-relative."""
    direct = resolve_path(project_root, characters_file)
    if direct.is_file():
        return direct
    relative = config_path.parent / characters_file
    if relative.is_file():
        return relative
    return direct


def resolve_locations_path(config_path: Path, locations_file: str | Path, project_root: Path = PROJECT_ROOT) -> Path:
    """Resolve location file path whether specified as project-relative or story-relative."""
    direct = resolve_path(project_root, locations_file)
    if direct.is_file():
        return direct
    relative = config_path.parent / locations_file
    if relative.is_file():
        return relative
    return direct


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Expected a JSON object in {path}")
    return data


def _load_character_entries(
    path: Path, project_root: Path
) -> dict[str, CharacterEntry]:
    """Parse character array from one JSON file into CharacterEntry objects."""
    if not path.is_file():
        return {}

    data = load_json(path)
    entries = data.get("characters")
    if entries is None:
        return {}
    if not isinstance(entries, list):
        raise ConfigError(f"{path} must contain a characters array")

    result: dict[str, CharacterEntry] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ConfigError(f"Every character in {path} must be an object")
        handle = entry.get("handle")
        name = entry.get("name", handle)
        reference_path = entry.get("reference_path")
        profile = entry.get("profile", "")
        description = entry.get("description", "")

        if not isinstance(handle, str) or not HANDLE_PATTERN.fullmatch(handle):
            raise ConfigError(f"Invalid character handle: {handle!r} in {path}")
        if not isinstance(reference_path, str) or not reference_path:
            raise ConfigError(f"Character {handle} in {path} has no reference_path")

        resolved_reference = resolve_path(project_root, reference_path)
        if not resolved_reference.is_file():
            raise ConfigError(
                f"Reference image for {handle} does not exist: {resolved_reference}"
            )

        extra = {k: v for k, v in entry.items() if k not in {"handle", "name", "reference_path", "profile", "description"}}

        result[handle] = CharacterEntry(
            handle=handle,
            name=name if isinstance(name, str) else handle,
            reference_path=reference_path,
            resolved_reference_path=resolved_reference,
            profile=profile if isinstance(profile, str) else "",
            description=description if isinstance(description, str) else "",
            extra=extra,
        )
    return result


def load_characters(
    path_or_root: Path = PROJECT_ROOT,
    story_or_root: Path | str | None = None,
) -> dict[str, CharacterEntry]:
    """Load and merge two-tier character registry.
    
    Supports both signatures:
    - load_characters(project_root, story_characters_path)
    - load_characters(story_characters_path, project_root)
    """
    if isinstance(path_or_root, Path) and path_or_root.is_file():
        story_characters_path = path_or_root
        project_root = story_or_root if isinstance(story_or_root, Path) and story_or_root.is_dir() else PROJECT_ROOT
    else:
        project_root = path_or_root if isinstance(path_or_root, Path) and path_or_root.is_dir() else PROJECT_ROOT
        story_characters_path = Path(story_or_root) if story_or_root else None

    global_path = project_root / "characters.json"
    characters = _load_character_entries(global_path, project_root) if global_path.is_file() else {}

    if story_characters_path is not None:
        story_path = resolve_path(project_root, story_characters_path)
        if story_path.is_file() and story_path != global_path:
            story_chars = _load_character_entries(story_path, project_root)
            # Story entries override or add to global registry
            for handle, entry in story_chars.items():
                if handle in characters:
                    # Inherit global profile/description if story entry left them empty
                    merged_profile = entry.profile or characters[handle].profile
                    merged_desc = entry.description or characters[handle].description
                    characters[handle] = CharacterEntry(
                        handle=handle,
                        name=entry.name or characters[handle].name,
                        reference_path=entry.reference_path,
                        resolved_reference_path=entry.resolved_reference_path,
                        profile=merged_profile,
                        description=merged_desc,
                        extra={**characters[handle].extra, **entry.extra},
                    )
                else:
                    characters[handle] = entry

    return characters


def _load_location_entries(
    path: Path, project_root: Path
) -> dict[str, LocationEntry]:
    """Parse a location registry into LocationEntry objects."""
    if not path.is_file():
        return {}

    data = load_json(path)
    entries = data.get("locations")
    if entries is None:
        return {}
    if not isinstance(entries, list):
        raise ConfigError(f"{path} must contain a locations array")

    result: dict[str, LocationEntry] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ConfigError(f"Every location in {path} must be an object")
        handle = entry.get("handle")
        name = entry.get("name", handle)
        reference_path = entry.get("reference_path")
        profile = entry.get("profile", "")
        description = entry.get("description", "")

        if (
            not isinstance(handle, str)
            or not HANDLE_PATTERN.fullmatch(handle)
            or not handle.startswith(LOCATION_HANDLE_PREFIX)
        ):
            raise ConfigError(
                f"Invalid location handle: {handle!r} in {path}; "
                f"expected {LOCATION_HANDLE_PREFIX}<identity>"
            )
        if handle in result:
            raise ConfigError(f"Duplicate location handle: {handle} in {path}")
        if not isinstance(reference_path, str) or not reference_path:
            raise ConfigError(f"Location {handle} in {path} has no reference_path")

        resolved_reference = resolve_path(project_root, reference_path)
        if not resolved_reference.is_file():
            raise ConfigError(
                f"Reference image for {handle} does not exist: {resolved_reference}"
            )

        extra = {
            k: v
            for k, v in entry.items()
            if k not in {"handle", "name", "reference_path", "profile", "description"}
        }
        result[handle] = LocationEntry(
            handle=handle,
            name=name if isinstance(name, str) else handle,
            reference_path=reference_path,
            resolved_reference_path=resolved_reference,
            profile=profile if isinstance(profile, str) else "",
            description=description if isinstance(description, str) else "",
            extra=extra,
        )
    return result


def load_locations(
    path_or_root: Path = PROJECT_ROOT,
    story_or_root: Path | str | None = None,
) -> dict[str, LocationEntry]:
    """Load and merge studio/project location registries, project entries winning."""
    if isinstance(path_or_root, Path) and path_or_root.is_file():
        story_locations_path = path_or_root
        project_root = (
            story_or_root
            if isinstance(story_or_root, Path) and story_or_root.is_dir()
            else PROJECT_ROOT
        )
    else:
        project_root = (
            path_or_root
            if isinstance(path_or_root, Path) and path_or_root.is_dir()
            else PROJECT_ROOT
        )
        story_locations_path = Path(story_or_root) if story_or_root else None

    global_path = project_root / "locations.json"
    locations = (
        _load_location_entries(global_path, project_root)
        if global_path.is_file()
        else {}
    )

    if story_locations_path is not None:
        story_path = resolve_path(project_root, story_locations_path)
        if story_path.is_file() and story_path != global_path:
            story_locations = _load_location_entries(story_path, project_root)
            for handle, entry in story_locations.items():
                if handle in locations:
                    base = locations[handle]
                    locations[handle] = LocationEntry(
                        handle=handle,
                        name=entry.name or base.name,
                        reference_path=entry.reference_path,
                        resolved_reference_path=entry.resolved_reference_path,
                        profile=entry.profile or base.profile,
                        description=entry.description or base.description,
                        extra={**base.extra, **entry.extra},
                    )
                else:
                    locations[handle] = entry

    return locations


def compile_scene(
    scene: dict[str, Any],
    characters: dict[str, CharacterEntry],
    project_root: Path = PROJECT_ROOT,
    first_frame: Path | None = None,
    *,
    locations: dict[str, LocationEntry] | None = None,
) -> CompiledScene:
    """Compile one scene, resolving character/location visuals and narration voices."""
    locations = locations or {}
    scene_id = scene.get("id", "unknown")
    prompt = scene.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ConfigError(f"Scene {scene_id} is waiting for a non-empty prompt")

    raw_prompt = prompt
    subjects = scene.get("subjects", [])
    location_declarations = scene.get("locations", [])
    if not isinstance(subjects, list) or not all(isinstance(item, str) for item in subjects):
        raise ConfigError(f"Scene {scene_id} subjects must be an array of handles")
    if not isinstance(location_declarations, list) or not all(
        isinstance(item, str) for item in location_declarations
    ):
        raise ConfigError(f"Scene {scene_id} locations must be an array of handles")
    if len(subjects) != len(set(subjects)):
        raise ConfigError(f"Scene {scene_id} contains duplicate subject handles")
    if len(location_declarations) != len(set(location_declarations)):
        raise ConfigError(f"Scene {scene_id} contains duplicate location handles")

    prompt_handle_order = list(dict.fromkeys(HANDLE_PATTERN.findall(prompt)))
    narration_handles = [
        handle for handle in prompt_handle_order
        if handle.startswith(NARRATION_HANDLE_PREFIX)
    ]
    location_prompt_handles = [
        handle for handle in prompt_handle_order
        if handle.startswith(LOCATION_HANDLE_PREFIX)
    ]
    character_prompt_handles = [
        handle for handle in prompt_handle_order
        if handle not in narration_handles and handle not in location_prompt_handles
    ]

    subject_handles = set(subjects)
    declared_location_handles = set(location_declarations)
    prompt_character_handles = set(character_prompt_handles)
    prompt_location_handles = set(location_prompt_handles)

    missing_characters_from_prompt = subject_handles - prompt_character_handles
    missing_characters_from_subjects = prompt_character_handles - subject_handles
    missing_locations_from_prompt = declared_location_handles - prompt_location_handles
    missing_locations_from_declarations = prompt_location_handles - declared_location_handles
    if missing_characters_from_prompt:
        raise ConfigError(
            f"Scene {scene_id} subjects absent from prompt: "
            f"{sorted(missing_characters_from_prompt)}"
        )
    if missing_characters_from_subjects:
        raise ConfigError(
            f"Scene {scene_id} prompt character handles absent from subjects: "
            f"{sorted(missing_characters_from_subjects)}"
        )
    if missing_locations_from_prompt:
        raise ConfigError(
            f"Scene {scene_id} locations absent from prompt: "
            f"{sorted(missing_locations_from_prompt)}"
        )
    if missing_locations_from_declarations:
        raise ConfigError(
            f"Scene {scene_id} prompt location handles absent from locations: "
            f"{sorted(missing_locations_from_declarations)}"
        )

    unknown_characters = subject_handles - set(characters)
    unknown_locations = declared_location_handles - set(locations)
    if unknown_characters:
        raise ConfigError(
            f"Scene {scene_id} uses unknown character handles: "
            f"{sorted(unknown_characters)}"
        )
    if unknown_locations:
        raise ConfigError(
            f"Scene {scene_id} uses unknown location handles: "
            f"{sorted(unknown_locations)}"
        )

    voices = load_voices(project_root)
    unknown_narration = set(narration_handles) - set(voices)
    if unknown_narration:
        raise ConfigError(
            f"Scene {scene_id} uses unknown narration handles: {sorted(unknown_narration)}"
        )

    # Preserve the authored order for every visual handle, regardless of type.
    visual_handle_order = [
        handle for handle in prompt_handle_order if handle not in narration_handles
    ]
    token_by_handle = {
        handle: f"<IMAGE_REF_{index}>"
        for index, handle in enumerate(visual_handle_order)
    }
    images: list[Path] = []
    declarations: list[str] = []
    next_image_number = 1

    voice_brief = ""
    if narration_handles:
        voice_lines = ["NARRATION VOICE PROFILES:"]
        for handle in narration_handles:
            voice_lines.append(f"- {handle}: {voices[handle]}")
        voice_lines.append(
            "These @narration-* handles are off-screen voice identities only. "
            "Never visualize them as people or characters."
        )
        voice_brief = "\n".join(voice_lines)

    if first_frame is not None:
        if not first_frame.is_file():
            raise ConfigError(f"Continuity frame does not exist: {first_frame}")
        images.append(first_frame)
        declarations.append(f"[# Sources <FIRST_FRAME>@Image{next_image_number}]")
        next_image_number += 1
        if "<FIRST_FRAME>" not in prompt:
            prompt = f"<FIRST_FRAME> {prompt}"

    for handle in visual_handle_order:
        token = token_by_handle[handle]
        entry: CharacterEntry | LocationEntry
        if handle.startswith(LOCATION_HANDLE_PREFIX):
            entry = locations[handle]
        else:
            entry = characters[handle]
        ref_path = entry.resolved_reference_path
        if not ref_path.is_file():
            raise ConfigError(
                f"Resolved reference image for {handle} is missing or invalid: {ref_path}"
            )
        images.append(ref_path)
        declarations.append(f"[# References {token}@Image{next_image_number}]")
        next_image_number += 1

    prompt = HANDLE_PATTERN.sub(
        lambda match: (
            match.group(0)
            if match.group(0).startswith(NARRATION_HANDLE_PREFIX)
            else token_by_handle[match.group(0)]
        ),
        prompt,
    )

    reference_images = scene.get("reference_images", [])
    if not isinstance(reference_images, list):
        raise ConfigError(f"Scene {scene_id} reference_images must be an array")
    for item in reference_images:
        if isinstance(item, str):
            configured_path = item
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            configured_path = item["path"]
        else:
            raise ConfigError(
                f"Scene {scene_id} reference_images entries must be paths or path objects"
            )
        path = resolve_path(project_root, configured_path)
        if not path.is_file():
            raise ConfigError(f"Scene {scene_id} reference image does not exist: {path}")
        reference_index = len(images) - (1 if first_frame is not None else 0)
        token = f"<IMAGE_REF_{reference_index}>"
        images.append(path)
        declarations.append(f"[# References {token}@Image{next_image_number}]")
        next_image_number += 1

    char_brief = format_character_brief(
        character_prompt_handles,
        characters,
        token_by_handle=token_by_handle,
    )
    location_brief = format_location_brief(
        location_prompt_handles,
        locations,
        token_by_handle=token_by_handle,
    )
    prompt_blocks = []
    if declarations:
        prompt_blocks.append("\n".join(declarations))
    if first_frame is not None:
        if len(images) > 1:
            prompt_blocks.append(
                "FIRST FRAME ROLE: Use Image1 as the literal starting frame at time 0. "
                "Preserve its composition, camera position, subject placement, costume, props, "
                "lighting, background people, and environment geometry exactly at the start. "
                "Use every other supplied image only as identity/environment reference material; "
                "do not use them as alternate starting frames and do not recompose Image1 before motion begins."
            )
        else:
            prompt_blocks.append(
                "FIRST FRAME ROLE: Use Image1 as the literal starting frame at time 0 and preserve "
                "its composition exactly before motion begins."
            )
    if char_brief:
        prompt_blocks.append(char_brief)
    if location_brief:
        prompt_blocks.append(location_brief)
    if voice_brief:
        prompt_blocks.append(voice_brief)
    prompt_blocks.append(prompt)
    compiled_prompt = "\n\n".join(prompt_blocks)

    flow_character_brief = format_flow_character_brief(
        character_prompt_handles, characters
    )
    flow_location_brief = format_flow_location_brief(
        location_prompt_handles, locations
    )
    flow_blocks = []
    if flow_character_brief:
        flow_blocks.append(flow_character_brief)
    if flow_location_brief:
        flow_blocks.append(flow_location_brief)
    if voice_brief:
        flow_blocks.append(voice_brief)
    flow_blocks.append(raw_prompt)
    flow_prompt = "\n\n".join(flow_blocks)

    if first_frame is not None and len(images) == 1:
        task = "image_to_video"
    else:
        task = "reference_to_video" if images else "text_to_video"

    return CompiledScene(
        prompt=compiled_prompt,
        images=images,
        task=task,
        handle_order=visual_handle_order,
        raw_prompt=raw_prompt,
        annotated_prompt=flow_prompt,
        flow_prompt=flow_prompt,
    )


def format_character_brief(
    handles: Sequence[str],
    characters: dict[str, CharacterEntry],
    *,
    include_description: bool = False,
    token_by_handle: dict[str, str] | None = None,
) -> str:
    """Format model-facing character profiles, optionally with narrative context."""
    if not handles:
        return ""
    lines = ["CHARACTER MORPHOLOGY & PROFILES:"]
    for idx, handle in enumerate(handles):
        token = token_by_handle[handle] if token_by_handle else f"<IMAGE_REF_{idx}>"
        if handle in characters:
            c = characters[handle]
            lines.append(f"- {token} ({handle}, {c.name}):")
            if c.profile:
                lines.append(f"  {c.profile}")
            if include_description and c.description and c.description != c.profile:
                lines.append(f"  {c.description}")
        else:
            lines.append(f"- {token} ({handle}): [Unregistered character]")
    return "\n".join(lines)


def format_location_brief(
    handles: Sequence[str],
    locations: dict[str, LocationEntry],
    *,
    include_description: bool = False,
    token_by_handle: dict[str, str] | None = None,
) -> str:
    """Format Google-facing recurring-location grounding without label-like text.

    Human-readable location names and prose profiles are intentionally omitted here.
    Gemini Omni has been observed to turn those metadata strings into visible signage.
    The ordered reference image plus the authored scene prompt own the visible location.
    Flow keeps its separate richer location brief below.
    """
    if not handles:
        return ""
    lines = [
        "LOCATION REFERENCE BINDINGS — metadata only; never render these tokens or metadata as visible text:"
    ]
    for idx, handle in enumerate(handles):
        token = token_by_handle[handle] if token_by_handle else f"<IMAGE_REF_{idx}>"
        if handle in locations:
            lines.append(
                f"- {token} is the recurring environment reference for {handle}; "
                "match its physical layout and visual identity."
            )
        else:
            lines.append(f"- {token} ({handle}): [Unregistered location]")
    return "\n".join(lines)


def format_flow_character_brief(
    handles: Sequence[str],
    characters: dict[str, CharacterEntry],
) -> str:
    """Format one-time Flow-facing character profiles keyed by project handle."""
    if not handles:
        return ""
    lines = ["CHARACTER MORPHOLOGY & PROFILES:"]
    for handle in handles:
        if handle in characters:
            c = characters[handle]
            lines.append(f"- {handle} ({c.name}):")
            if c.profile:
                lines.append(f"  {c.profile}")
        else:
            lines.append(f"- {handle}: [Unregistered character]")
    return "\n".join(lines)


def format_flow_location_brief(
    handles: Sequence[str],
    locations: dict[str, LocationEntry],
) -> str:
    """Format one-time Flow-facing location profiles keyed by project handle."""
    if not handles:
        return ""
    lines = ["LOCATION PROFILES:"]
    for handle in handles:
        if handle in locations:
            location = locations[handle]
            lines.append(f"- {handle} ({location.name}):")
            if location.profile:
                lines.append(f"  {location.profile}")
        else:
            lines.append(f"- {handle}: [Unregistered location]")
    return "\n".join(lines)


class BaseProvider(abc.ABC):
    """Abstract base provider for video generation backends."""

    name: str = "base"

    @abc.abstractmethod
    def preflight(self) -> bool:
        """Check provider health, authentication, or connection."""

    @abc.abstractmethod
    def generate_video(
        self,
        *,
        prompt: str,
        output: Path,
        images: Sequence[Path] = (),
        videos: Sequence[Path] = (),
        task: str | None = None,
        aspect_ratio: str = "16:9",
        duration: int = 10,
        model: str | None = None,
        **kwargs: Any,
    ) -> int:
        """Generate one video, write it to output path, and return its byte length."""
