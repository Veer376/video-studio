from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol, Sequence

from .io_utils import read_json, write_json_atomic
from .models import ReferenceInput


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class ProviderError(RuntimeError):
    pass


class ProviderNoResultRejection(ProviderError):
    """Explicit provider rejection known to have produced no creative result."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ImageProvider(Protocol):
    name: str

    def generate(
        self,
        *,
        prompt: str,
        output: Path,
        references: Sequence[ReferenceInput],
        model: str,
        aspect_ratio: str,
        idempotency_key: str | None = None,
    ) -> None: ...


@dataclass(frozen=True)
class VideoSubmission:
    job_id: str | None
    status: str
    items: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class VideoPoll:
    status: str
    items: tuple[dict[str, Any], ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class PreparedFlowVideo:
    body: dict[str, Any]


class FlowImageProvider:
    name = "flow"

    def __init__(self, cache: "FlowMediaCache | None" = None) -> None:
        from studio.images.providers import flow

        self.flow = flow
        self.cache = cache or FlowMediaCache()
        self._ready = False

    def _history_media_id_for_path(self, path: Path, *, base: str) -> str | None:
        """Reuse a media ID already issued for these exact reference bytes.

        Flow's historical `/v1/flow/uploadImage` endpoint can temporarily lag the
        modern web product's auth surface.  The local Flow history already stores
        the remote media ID and SHA-256 of every successful upload/generated file,
        so re-uploading identical bytes is unnecessary.
        """

        raw_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        cached = self.cache.get(raw_digest)
        if cached:
            return cached

        # `/v1/upload` normalizes images to PNG before sending them to Flow.  Its
        # history fingerprint is therefore the normalized PNG digest rather than
        # necessarily the source-file digest.
        try:
            data_uri = self.flow._reference_png_data_uri(path)
            encoded = data_uri.split(",", 1)[1]
            upload_digest = hashlib.sha256(base64.b64decode(encoded)).hexdigest()
        except Exception:
            upload_digest = raw_digest

        try:
            history = _request_json(f"{base}/v1/history", timeout=10).get("history") or []
        except Exception:
            history = []
        candidates = [
            item
            for item in history
            if isinstance(item, dict)
            and str(item.get("fingerprint") or "") in {raw_digest, upload_digest}
            and str(item.get("media_id") or "").strip()
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda item: int(item.get("timestamp") or 0), reverse=True)
        media_id = str(candidates[0]["media_id"])
        self.cache.put(raw_digest, media_id)
        return media_id

    def _reference_media_id(self, path: Path, *, base: str) -> str:
        existing = self._history_media_id_for_path(path, base=base)
        if existing:
            return existing
        try:
            media_id = self.flow.upload_reference(path, base_url=base)
        except Exception as exc:
            detail = str(exc)
            if "invalid authentication credentials" in detail.lower():
                raise ProviderNoResultRejection(
                    "FLOW_REFERENCE_UPLOAD_AUTH_FAILED",
                    f"Flow reference upload was rejected before image generation: {detail}",
                ) from exc
            raise
        self.cache.put(hashlib.sha256(path.read_bytes()).hexdigest(), media_id)
        return media_id

    def generate(
        self,
        *,
        prompt: str,
        output: Path,
        references: Sequence[ReferenceInput],
        model: str,
        aspect_ratio: str,
        idempotency_key: str | None = None,
    ) -> None:
        if not self._ready:
            self.flow.require_ready()
            self._ready = True
        normalized = self.flow.normalize_model(model)
        mapped = [SimpleNamespace(path=ref.path, role=ref.role) for ref in references]
        if not idempotency_key:
            raise ProviderError("Flow image generation requires an idempotency key")
        if aspect_ratio not in self.flow.ASPECT_TO_SIZE:
            raise ProviderError(f"Unsupported Flow aspect ratio: {aspect_ratio}")
        base = self.flow.resolve_base_url()
        ref_media_ids = [self._reference_media_id(reference.path, base=base) for reference in mapped]
        effective_prompt = (
            f"{self.flow._reference_instruction(mapped)} {prompt}" if mapped else prompt
        )
        body: dict[str, object] = {
            "prompt": effective_prompt,
            "model": normalized,
            "n": 1,
            "size": self.flow.ASPECT_TO_SIZE[aspect_ratio],
        }
        if ref_media_ids:
            body["ref_media_ids"] = ref_media_ids
        retry_delays = (2.0, 4.0, 8.0)
        for attempt in range(len(retry_delays) + 1):
            try:
                result = _request_json(
                    f"{base}/v1/images/generations",
                    body=body,
                    timeout=180,
                    headers={"Idempotency-Key": idempotency_key},
                )
                break
            except urllib.error.HTTPError as exc:
                detail = _http_error_detail(exc)
                if exc.code == 400 and "PUBLIC_ERROR_HIGH_TRAFFIC" in detail:
                    raise ProviderNoResultRejection(
                        "PUBLIC_ERROR_HIGH_TRAFFIC",
                        f"Flow image generation rejected before producing a result: HTTP 400: {detail}",
                    ) from exc
                if exc.code == 400 and (
                    "Could not revalidate history media ID" in detail
                    or "Could not validate media ID" in detail
                ):
                    raise ProviderNoResultRejection(
                        "FLOW_REFERENCE_REVALIDATION_FAILED",
                        f"Flow rejected the request during reference validation before generation: HTTP 400: {detail}",
                    ) from exc
                if exc.code in (429, 500, 502, 503, 504) and attempt < len(retry_delays):
                    time.sleep(retry_delays[attempt])
                    continue
                raise ProviderError(f"Flow image generation failed: HTTP {exc.code}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt < len(retry_delays):
                    time.sleep(retry_delays[attempt])
                    continue
                raise ProviderError(f"Flow image generation failed: {exc}") from exc
        else:
            raise ProviderError("Flow image generation failed without a response")
        items = result.get("data") or []
        if not isinstance(items, list) or not items:
            raise ProviderError(f"Flow returned no image media: {result}")
        url = str(items[0].get("url") or "")
        if not url:
            raise ProviderError(f"Flow returned image media without URL: {result}")
        self.flow._download_image_as_png(url, output)
        media_id = str(items[0].get("media_id") or "").strip()
        if media_id:
            self.cache.put(hashlib.sha256(output.read_bytes()).hexdigest(), media_id)


class GoogleImageProvider:
    name = "google"

    def __init__(self) -> None:
        from studio.images.providers import google

        self.google = google
        self._client: object | None = None

    def _create_client(self) -> object:
        """Prefer Gemini Developer API when a key is already configured.

        The legacy image provider is Vertex-only. For one-off production this
        unnecessarily couples image generation to Cloud billing even when the
        user already has a Gemini Developer API key. Keep the production layer
        scripts-only and select the existing credential surface without ever
        exposing the credential value.
        """
        developer_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GOOGLE_GENAI_API_KEY")
        )
        if developer_key:
            try:
                from google import genai
            except ImportError as exc:
                raise ProviderError("Google image generation requires google-genai") from exc
            return genai.Client(api_key=developer_key)
        return self.google.create_client()

    def generate(
        self,
        *,
        prompt: str,
        output: Path,
        references: Sequence[ReferenceInput],
        model: str,
        aspect_ratio: str,
        idempotency_key: str | None = None,
    ) -> None:
        if self._client is None:
            self._client = self._create_client()
        normalized = self.google.normalize_model(model)
        mapped = [SimpleNamespace(path=ref.path, role=ref.role) for ref in references]
        self.google.generate_image(
            client=self._client,
            model=normalized,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            out_path=output,
            reference_images=mapped,
        )


def make_image_provider(name: str) -> ImageProvider:
    normalized = name.strip().lower()
    if normalized == "flow":
        return FlowImageProvider()
    if normalized == "google":
        return GoogleImageProvider()
    raise ProviderError(f"Unsupported image provider: {name}")


def _request_json(
    url: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: int = 30,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request_headers = dict(headers or {})
    if payload is not None:
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(
        url,
        data=payload,
        headers=request_headers,
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    value = json.loads(raw or "{}")
    if not isinstance(value, dict):
        raise ProviderError(f"Expected object response from {url}")
    return value


def _http_error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        value = json.loads(exc.read().decode("utf-8", errors="replace"))
        return str(value.get("detail") or value)
    except Exception:
        return str(exc)


class FlowMediaCache:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".cache/kathamind-visuals/flow-media.json")
        if self.path.is_file():
            data = read_json(self.path)
            self.data = data if isinstance(data, dict) else {}
        else:
            self.data: dict[str, str] = {}

    def get(self, digest: str) -> str | None:
        value = self.data.get(digest)
        return str(value) if value else None

    def put(self, digest: str, media_id: str) -> None:
        self.data[digest] = media_id
        write_json_atomic(self.path, self.data)

    def remove(self, digest: str) -> None:
        if digest in self.data:
            del self.data[digest]
            write_json_atomic(self.path, self.data)


class FlowVideoProvider:
    name = "flow"
    CREDIT_COSTS = {4: 5, 6: 10, 8: 15, 10: 20}
    MODEL_MAP = {
        "omni_flash": None,
        "omni-flash": None,
        "gemini-omni-flash-preview": None,
        "gemini-omni-flash": None,
        "default": None,
        "veo": "veo_2",
        "veo_2": "veo_2",
    }

    def __init__(self, base_url: str | None = None, cache: FlowMediaCache | None = None) -> None:
        self.base = (base_url or os.environ.get("FLOW_AGENT_URL") or "http://127.0.0.1:8001").rstrip("/")
        self.cache = cache or FlowMediaCache()
        self._preflight_done = False

    def preflight(self) -> None:
        if self._preflight_done:
            return
        try:
            health = _request_json(f"{self.base}/health", timeout=5)
        except Exception as exc:
            raise ProviderError(
                f"Flow backend not reachable at {self.base}; start it with ~/.local/bin/flow"
            ) from exc
        if not health.get("extension_connected"):
            raise ProviderError("Flow Chrome extension is not connected")
        if not health.get("has_flow_key"):
            raise ProviderError("Flow authentication key has not been captured")
        self._preflight_done = True

    def check_credits(self, duration: int) -> None:
        required = self.CREDIT_COSTS.get(duration)
        if required is None:
            raise ProviderError(f"Flow duration must be one of {sorted(self.CREDIT_COSTS)}")
        try:
            data = _request_json(f"{self.base}/v1/credits", timeout=10)
        except Exception as exc:
            raise ProviderError(f"Could not verify Flow credits before paid submission: {exc}") from exc
        available = int(data.get("total_credits") or 0)
        if available < required:
            raise ProviderError(f"Insufficient Flow credits: {available} available, {required} required")

    def _media_valid(self, media_id: str) -> bool:
        try:
            value = _request_json(f"{self.base}/v1/media/{media_id}/url", timeout=10)
            return bool(value.get("url"))
        except Exception:
            return False

    def _upload(self, path: Path, label: str) -> tuple[str, bool]:
        if not path.is_file():
            raise ProviderError(f"{label} not found: {path}")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        cached = self.cache.get(digest)
        if cached and self._media_valid(cached):
            return cached, False
        if cached:
            self.cache.remove(digest)

        mime, _ = mimetypes.guess_type(path.name)
        if mime not in {"image/png", "image/jpeg", "image/webp", "video/mp4", "video/quicktime"}:
            mime = "image/png" if path.suffix.lower() == ".png" else "application/octet-stream"
        encoded = base64.b64encode(raw).decode("ascii")
        try:
            result = _request_json(
                f"{self.base}/v1/upload",
                body={"image_base64": f"data:{mime};base64,{encoded}"},
                timeout=240,
            )
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Flow upload failed for {label}: {_http_error_detail(exc)}") from exc
        media_id = str(result.get("media_id") or "")
        if not media_id:
            raise ProviderError(f"Flow upload returned no media_id for {label}: {result}")
        for _ in range(10):
            if self._media_valid(media_id):
                break
            time.sleep(1)
        else:
            raise ProviderError(
                f"Flow uploaded {label} but media {media_id} never became ready; refusing paid submission"
            )
        self.cache.put(digest, media_id)
        return media_id, True

    def prepare(
        self,
        *,
        prompt: str,
        start_frame: Path,
        end_frame: Path | None,
        duration: int,
        aspect_ratio: str,
        model: str,
        check_credits: bool = True,
    ) -> PreparedFlowVideo:
        self.preflight()
        if check_credits:
            self.check_credits(duration)
        start_id, fresh_start = self._upload(start_frame, "start frame")
        end_id: str | None = None
        fresh_end = False
        if end_frame is not None and end_frame.resolve() != start_frame.resolve():
            end_id, fresh_end = self._upload(end_frame, "end frame")
        if fresh_start or fresh_end:
            time.sleep(5)

        model_key = model.strip().lower()
        model_override = self.MODEL_MAP.get(model_key, model)
        body: dict[str, Any] = {
            "prompt": prompt,
            "duration": duration,
            "aspect": "portrait" if aspect_ratio == "9:16" else "landscape",
            "n": 1,
            "start_media_id": start_id,
        }
        if end_id:
            body["end_media_id"] = end_id
        if model_override:
            body["video_model"] = model_override

        return PreparedFlowVideo(body=body)

    def submit_prepared(
        self,
        *,
        prepared: PreparedFlowVideo,
        idempotency_key: str,
    ) -> VideoSubmission:
        body = dict(prepared.body)

        retry_delays = (3.0, 6.0, 10.0)
        for attempt in range(len(retry_delays) + 1):
            try:
                result = _request_json(
                    f"{self.base}/v1/videos/generations",
                    body=body,
                    timeout=240,
                    headers={"Idempotency-Key": idempotency_key},
                )
                break
            except urllib.error.HTTPError as exc:
                detail = _http_error_detail(exc)
                if exc.code in (429, 500, 502, 503, 504) and attempt < len(retry_delays):
                    time.sleep(retry_delays[attempt])
                    continue
                raise ProviderError(f"Flow video submission failed: HTTP {exc.code}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt < len(retry_delays):
                    time.sleep(retry_delays[attempt])
                    continue
                raise ProviderError(f"Flow video submission failed: {exc}") from exc
        else:
            raise ProviderError("Flow video submission failed without a response")

        job_id = str(result.get("job_id") or "") or None
        status = str(result.get("status") or "submitted")
        items = result.get("data") or []
        if not isinstance(items, list):
            items = []
        if status != "succeeded" and not job_id:
            raise ProviderError(f"Flow returned no job_id for non-terminal submission: {result}")
        return VideoSubmission(job_id=job_id, status=status, items=tuple(items))

    def submit(
        self,
        *,
        prompt: str,
        start_frame: Path,
        end_frame: Path | None,
        duration: int,
        aspect_ratio: str,
        model: str,
        idempotency_key: str,
        check_credits: bool = True,
    ) -> VideoSubmission:
        prepared = self.prepare(
            prompt=prompt,
            start_frame=start_frame,
            end_frame=end_frame,
            duration=duration,
            aspect_ratio=aspect_ratio,
            model=model,
            check_credits=check_credits,
        )
        return self.submit_prepared(
            prepared=prepared,
            idempotency_key=idempotency_key,
        )

    def poll_once(self, job_id: str) -> VideoPoll:
        try:
            result = _request_json(
                f"{self.base}/v1/videos/generations/{job_id}", timeout=15
            )
        except Exception as exc:
            return VideoPoll(status="poll_error", error=str(exc))
        status = str(result.get("status") or "unknown")
        items = result.get("data") or []
        if not isinstance(items, list):
            items = []
        error = result.get("error")
        if isinstance(error, dict):
            error = error.get("detail") or error
        return VideoPoll(status=status, items=tuple(items), error=str(error) if error else None)

    def download_items(self, items: Sequence[dict[str, Any]], output: Path) -> None:
        if not items:
            raise ProviderError("Flow video generation returned no media items")
        item = items[0]
        url = item.get("url")
        b64_data = item.get("b64_json")
        output.parent.mkdir(parents=True, exist_ok=True)
        if url:
            try:
                with urllib.request.urlopen(str(url), timeout=180) as response:
                    output.write_bytes(response.read())
            except Exception as exc:
                raise ProviderError(f"Failed to download Flow video: {exc}") from exc
        elif b64_data:
            output.write_bytes(base64.b64decode(str(b64_data)))
        else:
            raise ProviderError(f"Flow media item has neither url nor b64_json: {item}")


class GoogleVideoProvider:
    """Synchronous Google video adapter.

    The interaction API does not expose a resumable job id in the current reference
    implementation. The runner therefore marks the request uncertain before calling
    this provider and will never auto-resubmit it after a crash.
    """

    name = "google"

    def __init__(self, project: str | None = None) -> None:
        self.project = project
        self._client: Any = None

    def _client_instance(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import google.auth
            from google import genai
        except ImportError as exc:
            raise ProviderError("Google video generation requires google-genai") from exc
        project = self.project or os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT_ID")
        if not project:
            _, project = google.auth.default()
        if not project:
            raise ProviderError("Google Cloud project is unavailable")
        self._client = genai.Client(vertexai=True, project=project, location="global")
        return self._client

    @staticmethod
    def _image_input(path: Path) -> dict[str, str]:
        mime, _ = mimetypes.guess_type(path.name)
        mime = mime or "image/png"
        return {
            "type": "image",
            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
            "mime_type": mime,
        }

    def generate(
        self,
        *,
        prompt: str,
        start_frame: Path,
        end_frame: Path | None,
        output: Path,
        aspect_ratio: str,
        model: str,
    ) -> None:
        model_key = model.strip().lower()
        if model_key in {
            "omni_flash",
            "omni-flash",
            "gemini-omni-flash",
        }:
            model = "gemini-omni-flash-preview"

        inputs: list[dict[str, str]] = [self._image_input(start_frame)]
        if end_frame is not None and end_frame.resolve() != start_frame.resolve():
            inputs.append(self._image_input(end_frame))
            prompt = (
                "Use Image1 as the literal starting frame (<FIRST_FRAME>). Image2 is the intended "
                "later/end state. Create a grounded visual progression between them. "
                + prompt
            )
        else:
            prompt = "Use Image1 as the literal starting frame (<FIRST_FRAME>). " + prompt
        inputs.append({"type": "text", "text": prompt})
        client = self._client_instance()
        try:
            interaction = client.interactions.create(
                model=model,
                input=inputs,
                response_format={"type": "video", "aspect_ratio": aspect_ratio},
                generation_config={"video_config": {"task": "image_to_video"}},
                timeout=600,
            )
        except Exception as exc:
            raise ProviderError(f"Google video request failed: {exc}") from exc
        output_video = getattr(interaction, "output_video", None)
        data = getattr(output_video, "data", None)
        if not data:
            raise ProviderError("Google completed without inline video data")
        video_bytes = base64.b64decode(data) if isinstance(data, str) else bytes(data)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(video_bytes)

