from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .anchors import AnchorRegistry
from .io_utils import sha256_file, sha256_json
from .manifest import ManifestStore, utc_now
from .models import AssetNode, ProductionPlan, ReferenceInput
from .providers import (
    FlowVideoProvider,
    GoogleVideoProvider,
    ImageProvider,
    PreparedFlowVideo,
    ProviderNoResultRejection,
    make_image_provider,
)
from .references import image_references_for_node, video_frame_paths
from .verify import verify_image, verify_video


class ProductionError(RuntimeError):
    pass


FINGERPRINT_VERSION = 2


@dataclass(frozen=True)
class ProductionSettings:
    image_provider: str = "flow"
    image_model: str = "pro"
    video_provider: str | None = None
    video_model: str = "omni_flash"
    aspect_ratio: str = "16:9"
    flow_poll_seconds: float = 3.0
    flow_poll_timeout: float = 900.0
    skip_video_download: bool = False
    skip_video_credit_check: bool = False


@dataclass(frozen=True)
class RunResult:
    completed: tuple[str, ...]
    skipped: tuple[str, ...]
    blocked: tuple[str, ...]


def fingerprint_for(
    node: AssetNode,
    *,
    provider: str,
    model: str,
    aspect_ratio: str,
    references: Sequence[ReferenceInput],
) -> str:
    return sha256_json(
        {
            "fingerprint_version": FINGERPRINT_VERSION,
            "adapter_contract": "scripts-production-v1",
            "asset_id": node.asset_id,
            "kind": node.kind,
            "prompt": node.prompt,
            "provider": provider,
            "model": model,
            "aspect_ratio": aspect_ratio,
            "duration": node.duration,
            "start_asset_id": node.start_asset_id,
            "end_asset_id": node.end_asset_id,
            "references": [
                {"asset_id": ref.asset_id, "sha256": ref.sha256, "role": ref.role}
                for ref in references
            ],
        }
    )


def idempotency_key_for(
    node: AssetNode,
    fingerprint: str,
    *,
    project_dir: Path,
) -> str:
    project_namespace = sha256_json({"project_path": str(project_dir.resolve())})[:16]
    return f"kathamind-{project_namespace}-{node.kind}-{fingerprint}"


def flow_recovery_idempotency_key(rejected_key: str, rejection_code: str) -> str:
    """Derive a fresh deterministic key for an explicit no-result rejection.

    This is recovery of the same logical asset, not a creative attempt/candidate.
    """

    digest = sha256_json(
        {
            "rejected_idempotency_key": rejected_key,
            "rejection_code": rejection_code,
        }
    )
    return f"kathamind-flow-recovery-{digest}"


MAX_FLOW_NO_RESULT_RECOVERIES = 3


def _known_no_result_rejection(record: dict) -> str | None:
    code = str(record.get("provider_rejection") or "").strip()
    if code:
        return code
    # Backward compatibility for records written before typed rejection state
    # existed. This exact provider code is a known explicit no-result rejection.
    error = str(record.get("error") or "")
    if "PUBLIC_ERROR_HIGH_TRAFFIC" in error:
        return "PUBLIC_ERROR_HIGH_TRAFFIC"
    if (
        "Could not revalidate history media ID" in error
        or "Could not validate media ID" in error
    ):
        return "FLOW_REFERENCE_REVALIDATION_FAILED"
    if "invalid authentication credentials" in error.lower() and "reference upload" in error.lower():
        return "FLOW_REFERENCE_UPLOAD_AUTH_FAILED"
    return None


def _reference_records(references: Sequence[ReferenceInput]) -> list[dict[str, str]]:
    return [
        {
            "asset_id": ref.asset_id,
            "path": str(ref.path),
            "sha256": ref.sha256,
            "role": ref.role,
        }
        for ref in references
    ]


def dependency_closure(plan: ProductionPlan, asset_ids: Iterable[str]) -> set[str]:
    node_by_id = plan.node_by_id
    selected = set(asset_ids)
    stack = list(selected)
    while stack:
        asset_id = stack.pop()
        node = node_by_id.get(asset_id)
        if node is None:
            raise ProductionError(f"Unknown asset selected: {asset_id}")
        for dependency in node.dependencies:
            if dependency not in selected:
                selected.add(dependency)
                stack.append(dependency)
    return selected


def select_assets(
    plan: ProductionPlan,
    *,
    scene_ids: Sequence[str] = (),
    through_scene: str | None = None,
    phase: str = "all",
) -> set[str]:
    valid_scenes = set(plan.scene_order)
    requested_scenes = set(scene_ids)
    unknown = sorted(requested_scenes - valid_scenes)
    if unknown:
        raise ProductionError(f"Unknown scenes selected: {', '.join(unknown)}")
    if through_scene:
        if through_scene not in valid_scenes:
            raise ProductionError(f"Unknown --through scene: {through_scene}")
        through_index = plan.scene_order.index(through_scene)
        requested_scenes.update(plan.scene_order[: through_index + 1])
    if not requested_scenes:
        requested_scenes = set(plan.scene_order)

    if phase not in {"all", "images", "videos"}:
        raise ProductionError(f"Unsupported phase: {phase}")
    candidates = [
        node.asset_id
        for node in plan.nodes
        if node.scene_id in requested_scenes
        and (
            phase == "all"
            or (phase == "images" and node.kind != "video")
            or (phase == "videos" and node.kind == "video")
        )
    ]
    if phase == "videos":
        return set(candidates)
    return dependency_closure(plan, candidates)


class ProductionRunner:
    def __init__(
        self,
        *,
        plan: ProductionPlan,
        manifest: ManifestStore,
        anchors: AnchorRegistry,
        settings: ProductionSettings,
        image_provider: ImageProvider | None = None,
        flow_video_provider: FlowVideoProvider | None = None,
        google_video_provider: GoogleVideoProvider | None = None,
        image_verifier: Callable[[Path], None] = verify_image,
        video_verifier: Callable[[Path], None] = verify_video,
    ) -> None:
        self.plan = plan
        self.manifest = manifest
        self.anchors = anchors
        self.settings = settings
        if self.settings.aspect_ratio != self.plan.aspect_ratio:
            raise ProductionError(
                f"Production aspect ratio {self.settings.aspect_ratio} conflicts with locked "
                f"session.visual.aspect_ratio {self.plan.aspect_ratio}"
            )
        self.image_provider = image_provider
        self.flow_video_provider = flow_video_provider
        self.google_video_provider = google_video_provider
        self.image_verifier = image_verifier
        self.video_verifier = video_verifier

    def _output_path(self, node: AssetNode) -> Path:
        return self.plan.project_dir / node.output_rel

    def _is_current(self, node: AssetNode, fingerprint: str) -> bool:
        record = self.manifest.get(node.asset_id)
        if not record or record.get("status") != "complete":
            return False
        if record.get("fingerprint") != fingerprint:
            return False
        output = self._output_path(node)
        try:
            if node.kind == "video":
                self.video_verifier(output)
            else:
                self.image_verifier(output)
        except Exception:
            return False
        actual_sha = sha256_file(output)
        return record.get("output_sha256") == actual_sha

    def _ensure_safe_to_submit(self, node: AssetNode) -> None:
        record = self.manifest.get(node.asset_id)
        if not record:
            if self._output_path(node).exists():
                raise ProductionError(
                    f"Refusing to overwrite untracked output for {node.asset_id}: {self._output_path(node)}"
                )
            return
        status = str(record.get("status") or "")
        if status in {"submitting", "uncertain"}:
            raise ProductionError(
                f"{node.asset_id} is in uncertain state {status!r}; explicit retry is required "
                "after confirming the remote request is safe to repeat"
            )
        if status == "submitted" and not record.get("remote_job_id"):
            raise ProductionError(
                f"{node.asset_id} is submitted without a resumable job id; refusing automatic resubmission"
            )
        if status == "failed":
            raise ProductionError(
                f"{node.asset_id} previously failed; run the explicit retry command before spending again"
            )
        if status == "blocked":
            return

    def _generate_image(self, node: AssetNode) -> str:
        references = image_references_for_node(
            node,
            plan=self.plan,
            manifest=self.manifest,
            anchors=self.anchors,
        )
        provider_name = self.settings.image_provider
        model = self.settings.image_model
        fingerprint = fingerprint_for(
            node,
            provider=provider_name,
            model=model,
            aspect_ratio=self.settings.aspect_ratio,
            references=references,
        )
        if self._is_current(node, fingerprint):
            return "skipped"
        record = self.manifest.get(node.asset_id) or {}
        known_rejection = (
            _known_no_result_rejection(record)
            if provider_name == "flow" and record.get("fingerprint") == fingerprint
            else None
        )
        safe_flow_recovery = bool(
            provider_name == "flow"
            and known_rejection
            and record.get("idempotency_key")
            and record.get("status") in {"failed", "uncertain"}
        )
        safe_flow_replay = bool(
            provider_name == "flow"
            and record.get("fingerprint") == fingerprint
            and record.get("idempotency_key")
            and record.get("status") in {"submitting", "uncertain"}
            and not safe_flow_recovery
        )
        if not safe_flow_replay and not safe_flow_recovery:
            self._ensure_safe_to_submit(node)
        if self.image_provider is None:
            self.image_provider = make_image_provider(provider_name)
        output = self._output_path(node)
        if safe_flow_recovery:
            rejected_key = str(record["idempotency_key"])
            idempotency_key = flow_recovery_idempotency_key(
                rejected_key,
                str(known_rejection),
            )
        elif safe_flow_replay:
            idempotency_key = str(record["idempotency_key"])
        else:
            if provider_name == "flow":
                idempotency_key = idempotency_key_for(
                    node,
                    fingerprint,
                    project_dir=self.plan.project_dir,
                )
            else:
                self.manifest.increment_attempt(node.asset_id)
                idempotency_key = None
        recovery_count = 0
        while True:
            self.manifest.update(
                node.asset_id,
                scene_id=node.scene_id,
                kind=node.kind,
                output_path=node.output_rel,
                provider=provider_name,
                model=model,
                aspect_ratio=self.settings.aspect_ratio,
                fingerprint=fingerprint,
                idempotency_key=idempotency_key,
                references=_reference_records(references),
                status="submitting",
                provider_rejection=None,
                error=None,
            )
            try:
                self.image_provider.generate(
                    prompt=node.prompt,
                    output=output,
                    references=references,
                    model=model,
                    aspect_ratio=self.settings.aspect_ratio,
                    idempotency_key=idempotency_key,
                )
                self.image_verifier(output)
                output_sha = sha256_file(output)
                break
            except ProviderNoResultRejection as exc:
                rejected_key = str(idempotency_key)
                self.manifest.update(
                    node.asset_id,
                    status="failed",
                    provider_rejection=exc.code,
                    error=str(exc),
                )
                if recovery_count >= MAX_FLOW_NO_RESULT_RECOVERIES:
                    raise ProductionError(
                        f"Flow explicitly rejected {node.asset_id} with {exc.code} after "
                        f"{MAX_FLOW_NO_RESULT_RECOVERIES} automatic recoveries"
                    ) from exc
                recovery_count += 1
                time.sleep(min(2.0 * recovery_count, 6.0))
                idempotency_key = flow_recovery_idempotency_key(rejected_key, exc.code)
                self.manifest.update(
                    node.asset_id,
                    idempotency_key=idempotency_key,
                    recovery_of_idempotency_key=rejected_key,
                    recovery_reason=exc.code,
                    status="submitting",
                    provider_rejection=None,
                    error=None,
                )
                continue
            except Exception as exc:
                self.manifest.update(
                    node.asset_id,
                    status="uncertain",
                    provider_rejection=None,
                    error=(
                        "Provider call did not complete cleanly. The remote side may have accepted "
                        f"work, so automatic resubmission is disabled: {exc}"
                    ),
                )
                raise ProductionError(f"Image generation failed for {node.asset_id}: {exc}") from exc
        self.manifest.update(
            node.asset_id,
            status="complete",
            output_sha256=output_sha,
            verified_at=utc_now(),
            provider_rejection=None,
            error=None,
        )
        return "completed"

    def _video_provider_and_model(self, node: AssetNode) -> tuple[str, str]:
        provider = (self.settings.video_provider or node.provider_hint or "flow").lower()
        model = node.model_hint or self.settings.video_model
        if provider not in {"flow", "google"}:
            raise ProductionError(f"Unsupported video provider for {node.asset_id}: {provider}")
        return provider, model

    def _finish_flow_video(
        self,
        *,
        node: AssetNode,
        provider: FlowVideoProvider,
        job_id: str,
        fingerprint: str,
    ) -> str:
        partial = self._output_path(node).with_suffix(".partial.mp4")
        deadline = time.monotonic() + self.settings.flow_poll_timeout
        poll_errors = 0
        while time.monotonic() < deadline:
            poll = provider.poll_once(job_id)
            if poll.status == "poll_error":
                poll_errors += 1
                if poll_errors >= 8:
                    raise ProductionError(
                        f"Flow polling repeatedly failed for {node.asset_id}: {poll.error}"
                    )
                time.sleep(self.settings.flow_poll_seconds)
                continue
            poll_errors = 0
            self.manifest.update(
                node.asset_id,
                status="submitted",
                remote_job_id=job_id,
                remote_status=poll.status,
            )
            if poll.status == "failed":
                self.manifest.update(node.asset_id, status="failed", error=poll.error or "Flow job failed")
                raise ProductionError(f"Flow job failed for {node.asset_id}: {poll.error}")
            if poll.status == "succeeded":
                if self.settings.skip_video_download:
                    media_ids = [
                        str(item.get("media_id"))
                        for item in poll.items
                        if isinstance(item, dict) and item.get("media_id")
                    ]
                    self.manifest.update(
                        node.asset_id,
                        status="submitted",
                        fingerprint=fingerprint,
                        remote_job_id=job_id,
                        remote_status="succeeded",
                        remote_media_ids=media_ids,
                        remote_items=list(poll.items),
                        error=None,
                    )
                    return "completed"
                partial.unlink(missing_ok=True)
                try:
                    provider.download_items(poll.items, partial)
                    self.video_verifier(partial)
                    output = self._output_path(node)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(partial, output)
                    output_sha = sha256_file(output)
                finally:
                    partial.unlink(missing_ok=True)
                self.manifest.update(
                    node.asset_id,
                    status="complete",
                    fingerprint=fingerprint,
                    output_sha256=output_sha,
                    verified_at=utc_now(),
                    remote_status="succeeded",
                    error=None,
                )
                return "completed"
            time.sleep(self.settings.flow_poll_seconds)
        raise ProductionError(
            f"Flow job {job_id} for {node.asset_id} is still pending after {self.settings.flow_poll_timeout:.0f}s; rerun to resume polling"
        )

    def _generate_flow_video(
        self,
        node: AssetNode,
        *,
        start: ReferenceInput,
        end: ReferenceInput,
        fingerprint: str,
        model: str,
    ) -> str:
        record = self.manifest.get(node.asset_id) or {}
        if record.get("status") == "submitted" and record.get("remote_job_id"):
            if record.get("fingerprint") != fingerprint:
                raise ProductionError(
                    f"{node.asset_id} has an in-flight Flow job for an older fingerprint; "
                    "do not attach it to the changed prompt/references"
                )
            if self.flow_video_provider is None:
                self.flow_video_provider = FlowVideoProvider()
            return self._finish_flow_video(
                node=node,
                provider=self.flow_video_provider,
                job_id=str(record["remote_job_id"]),
                fingerprint=fingerprint,
            )

        safe_replay = bool(
            record.get("fingerprint") == fingerprint
            and record.get("idempotency_key")
            and record.get("status") in {"submitting", "uncertain", "submitted"}
        )
        if self.flow_video_provider is None:
            self.flow_video_provider = FlowVideoProvider()
        provider = self.flow_video_provider
        if safe_replay:
            idempotency_key = str(record["idempotency_key"])
            remote_request = record.get("remote_request")
            if not isinstance(remote_request, dict) or not remote_request:
                raise ProductionError(
                    f"{node.asset_id} is replayable but has no persisted Flow request body; manual reconciliation is required"
                )
            prepared = PreparedFlowVideo(body=dict(remote_request))
        else:
            self._ensure_safe_to_submit(node)
            try:
                prepared = provider.prepare(
                    prompt=node.prompt,
                    start_frame=start.path,
                    end_frame=end.path,
                    duration=int(node.duration or 10),
                    aspect_ratio=self.settings.aspect_ratio,
                    model=model,
                    check_credits=not self.settings.skip_video_credit_check,
                )
            except Exception as exc:
                self.manifest.update(
                    node.asset_id,
                    scene_id=node.scene_id,
                    kind=node.kind,
                    output_path=node.output_rel,
                    provider="flow",
                    model=model,
                    aspect_ratio=self.settings.aspect_ratio,
                    status="blocked",
                    preflight_error=str(exc),
                    preflight_failed_at=utc_now(),
                )
                raise ProductionError(
                    f"Flow pre-submit preparation failed for {node.asset_id}: {exc}"
                ) from exc
            idempotency_key = idempotency_key_for(
                node,
                fingerprint,
                project_dir=self.plan.project_dir,
            )
        self.manifest.update(
            node.asset_id,
            scene_id=node.scene_id,
            kind=node.kind,
            output_path=node.output_rel,
            provider="flow",
            model=model,
            aspect_ratio=self.settings.aspect_ratio,
            fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            remote_request=dict(prepared.body),
            references=_reference_records((start, end)),
            status="submitting",
            preflight_error=None,
            preflight_failed_at=None,
            error=None,
        )
        try:
            submission = provider.submit_prepared(
                prepared=prepared,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:
            self.manifest.update(
                node.asset_id,
                status="uncertain",
                error=(
                    "Flow submission did not complete cleanly and may have reached the remote "
                    f"service; automatic resubmission is disabled: {exc}"
                ),
            )
            raise ProductionError(f"Flow submission failed for {node.asset_id}: {exc}") from exc

        self.manifest.update(
            node.asset_id,
            status="submitted",
            remote_job_id=submission.job_id,
            remote_status=submission.status,
        )
        if submission.status == "succeeded":
            if self.settings.skip_video_download:
                media_ids = [
                    str(item.get("media_id"))
                    for item in submission.items
                    if isinstance(item, dict) and item.get("media_id")
                ]
                self.manifest.update(
                    node.asset_id,
                    status="submitted",
                    remote_job_id=submission.job_id,
                    remote_status="succeeded",
                    remote_media_ids=media_ids,
                    remote_items=list(submission.items),
                    error=None,
                )
                return "completed"
            partial = self._output_path(node).with_suffix(".partial.mp4")
            partial.unlink(missing_ok=True)
            try:
                provider.download_items(submission.items, partial)
                self.video_verifier(partial)
                output = self._output_path(node)
                output.parent.mkdir(parents=True, exist_ok=True)
                os.replace(partial, output)
                output_sha = sha256_file(output)
            finally:
                partial.unlink(missing_ok=True)
            self.manifest.update(
                node.asset_id,
                status="complete",
                output_sha256=output_sha,
                verified_at=utc_now(),
                remote_status="succeeded",
                error=None,
            )
            return "completed"
        if not submission.job_id:
            self.manifest.update(
                node.asset_id,
                status="uncertain",
                error="Flow submission returned no resumable job id",
            )
            raise ProductionError(f"Flow submission for {node.asset_id} cannot be resumed safely")
        return self._finish_flow_video(
            node=node,
            provider=provider,
            job_id=submission.job_id,
            fingerprint=fingerprint,
        )

    def _generate_google_video(
        self,
        node: AssetNode,
        *,
        start: ReferenceInput,
        end: ReferenceInput,
        fingerprint: str,
        model: str,
    ) -> str:
        self._ensure_safe_to_submit(node)
        if self.google_video_provider is None:
            self.google_video_provider = GoogleVideoProvider()
        output = self._output_path(node)
        partial = output.with_suffix(".partial.mp4")
        self.manifest.increment_attempt(node.asset_id)
        self.manifest.update(
            node.asset_id,
            scene_id=node.scene_id,
            kind=node.kind,
            output_path=node.output_rel,
            provider="google",
            model=model,
            aspect_ratio=self.settings.aspect_ratio,
            fingerprint=fingerprint,
            references=_reference_records((start, end)),
            status="submitting",
            error=None,
        )
        partial.unlink(missing_ok=True)
        try:
            self.google_video_provider.generate(
                prompt=node.prompt,
                start_frame=start.path,
                end_frame=end.path,
                output=partial,
                aspect_ratio=self.settings.aspect_ratio,
                model=model,
            )
            self.video_verifier(partial)
            output.parent.mkdir(parents=True, exist_ok=True)
            os.replace(partial, output)
            output_sha = sha256_file(output)
        except Exception as exc:
            partial.unlink(missing_ok=True)
            self.manifest.update(
                node.asset_id,
                status="uncertain",
                error=(
                    "Google video request failed or was interrupted after submission; "
                    f"automatic repeat is disabled: {exc}"
                ),
            )
            raise ProductionError(f"Google video generation uncertain for {node.asset_id}: {exc}") from exc
        self.manifest.update(
            node.asset_id,
            status="complete",
            output_sha256=output_sha,
            verified_at=utc_now(),
            error=None,
        )
        return "completed"

    def _generate_video(self, node: AssetNode) -> str:
        start, end = video_frame_paths(node, plan=self.plan, manifest=self.manifest)
        provider, model = self._video_provider_and_model(node)
        fingerprint = fingerprint_for(
            node,
            provider=provider,
            model=model,
            aspect_ratio=self.settings.aspect_ratio,
            references=(start, end),
        )
        if self._is_current(node, fingerprint):
            return "skipped"
        if provider == "flow":
            return self._generate_flow_video(
                node, start=start, end=end, fingerprint=fingerprint, model=model
            )
        return self._generate_google_video(
            node, start=start, end=end, fingerprint=fingerprint, model=model
        )

    def _assert_image_current_recursive(
        self, asset_id: str, *, visited: set[str] | None = None
    ) -> None:
        visited = visited or set()
        if asset_id in visited:
            return
        visited.add(asset_id)
        node = self.plan.node_by_id.get(asset_id)
        if node is None or node.kind == "video":
            raise ProductionError(f"Expected image dependency, got: {asset_id}")
        for dependency in node.dependencies:
            self._assert_image_current_recursive(dependency, visited=visited)
        record = self.manifest.get(asset_id)
        if not record or record.get("status") != "complete":
            raise ProductionError(f"Required image is incomplete: {asset_id}")
        references = image_references_for_node(
            node,
            plan=self.plan,
            manifest=self.manifest,
            anchors=self.anchors,
        )
        provider = str(record.get("provider") or self.settings.image_provider)
        model = str(record.get("model") or self.settings.image_model)
        aspect_ratio = str(record.get("aspect_ratio") or self.settings.aspect_ratio)
        expected = fingerprint_for(
            node,
            provider=provider,
            model=model,
            aspect_ratio=aspect_ratio,
            references=references,
        )
        if not self._is_current(node, expected):
            raise ProductionError(
                f"Required image {asset_id} is stale relative to current prompts/references; "
                "run the image phase before video generation"
            )

    def run(self, selected_asset_ids: set[str], *, phase: str = "all") -> RunResult:
        completed: list[str] = []
        skipped: list[str] = []
        blocked: list[str] = []
        node_by_id = self.plan.node_by_id

        image_nodes = [
            node
            for node in self.plan.nodes
            if node.asset_id in selected_asset_ids and node.kind != "video"
        ]
        if phase != "videos":
            for node in image_nodes:
                try:
                    result = self._generate_image(node)
                except Exception:
                    blocked.extend(
                        dependent.asset_id
                        for dependent in image_nodes
                        if node.asset_id in dependent.dependencies
                    )
                    raise
                (skipped if result == "skipped" else completed).append(node.asset_id)

        video_nodes = [
            node
            for node in self.plan.nodes
            if node.asset_id in selected_asset_ids and node.kind == "video"
        ]
        if phase != "images":
            for node in video_nodes:
                try:
                    for dependency in node.dependencies:
                        self._assert_image_current_recursive(dependency)
                except Exception:
                    blocked.append(node.asset_id)
                    raise
                result = self._generate_video(node)
                (skipped if result == "skipped" else completed).append(node.asset_id)

        return RunResult(tuple(completed), tuple(skipped), tuple(dict.fromkeys(blocked)))

