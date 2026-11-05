from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from .io_utils import read_json, write_json_atomic


ANCHOR_VERSION = 1


@dataclass(frozen=True)
class AnchorBinding:
    asset_id: str
    output_sha256: str
    fingerprint: str


class AnchorRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path
        if path.is_file():
            data = read_json(path)
            if data.get("version") != ANCHOR_VERSION:
                raise ValueError(f"Unsupported anchor registry version: {data.get('version')}")
            self.data = data
        else:
            self.data = {"version": ANCHOR_VERSION, "subjects": {}, "locations": {}}
        for field in ("subjects", "locations"):
            if not isinstance(self.data.get(field), dict):
                raise ValueError(f"anchor registry {field} must be an object")

    @staticmethod
    def _binding(value: object, *, label: str) -> AnchorBinding | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError(
                f"{label} uses an unpinned legacy anchor; approve it again so exact bytes are bound"
            )
        asset_id = value.get("asset_id")
        output_sha256 = value.get("output_sha256")
        fingerprint = value.get("fingerprint")
        if not all(isinstance(item, str) and item for item in (asset_id, output_sha256, fingerprint)):
            raise ValueError(f"{label} anchor is missing asset_id/output_sha256/fingerprint")
        return AnchorBinding(asset_id, output_sha256, fingerprint)

    def get_subject(self, subject_id: str) -> AnchorBinding | None:
        value = self.data["subjects"].get(subject_id)
        return self._binding(value, label=f"subject {subject_id}")

    def get_location(self, location_id: str) -> AnchorBinding | None:
        value = self.data["locations"].get(location_id)
        return self._binding(value, label=f"location {location_id}")

    def set_subject(
        self, subject_id: str, asset_id: str, *, output_sha256: str, fingerprint: str
    ) -> None:
        self.data["subjects"][subject_id] = {
            "asset_id": asset_id,
            "output_sha256": output_sha256,
            "fingerprint": fingerprint,
        }
        write_json_atomic(self.path, self.data)

    def set_location(
        self, location_id: str, asset_id: str, *, output_sha256: str, fingerprint: str
    ) -> None:
        self.data["locations"][location_id] = {
            "asset_id": asset_id,
            "output_sha256": output_sha256,
            "fingerprint": fingerprint,
        }
        write_json_atomic(self.path, self.data)

