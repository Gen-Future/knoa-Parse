"""Controlled FFmpeg audio extraction for planned ASR chunks."""
import hashlib
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from knoa_parse.core.asr import AsrProvider, AsrRequest, AsrResponse, AsrUsage, PreparedAudioSegment
from knoa_parse.core.errors import ParseError, ProviderError
from knoa_parse.core.provider_runs import ProviderUsage
from knoa_parse.core.media import MediaProbeInput
from knoa_parse.core.media_results import MediaChunkOutcome, MediaExecutionSummary, MediaInvocationPort, MediaInvocationUnit
from knoa_parse.core.models import Artifact, Model
from knoa_parse.core.timeline import AudioChunk

from .coverage import require_audio_stream, summarize_execution
from .source import StagedMedia
from .process import BoundedProcessError, run_bounded
from .timeline import MediaTimelineError, plan_audio_chunks


class FfmpegError(ParseError):
    """Sanitized error from the external FFmpeg process."""


@dataclass(frozen=True)
class FfmpegConfig:
    executable: str = "ffmpeg"
    timeout_seconds: float = 120.0
    max_output_bytes: int = 64 * 1024 * 1024
    sample_rate: int = 16000
    channels: int = 1

    def __post_init__(self):
        if not isinstance(self.executable, str) or not self.executable.strip() \
                or any(ord(c) < 32 for c in self.executable):
            raise ValueError("Invalid FFmpeg executable")
        if type(self.timeout_seconds) not in {int, float} or not math.isfinite(self.timeout_seconds) \
                or not 0.1 <= self.timeout_seconds <= 900:
            raise ValueError("FFmpeg timeout is outside the allowed range")
        if type(self.max_output_bytes) is not int or not 1024 <= self.max_output_bytes <= 512 * 1024 * 1024:
            raise ValueError("FFmpeg output limit is outside the allowed range")
        if type(self.sample_rate) is not int or not 8000 <= self.sample_rate <= 96000:
            raise ValueError("FFmpeg sample rate is outside the allowed range")
        if type(self.channels) is not int or not 1 <= self.channels <= 2:
            raise ValueError("FFmpeg channel count is outside the allowed range")


class AudioExtractor(Protocol):
    def extract(self, source: StagedMedia, chunk: AudioChunk, *, timeout_seconds: float | None = None) -> PreparedAudioSegment: ...


class FfmpegAudioExtractor:
    """Extract one chunk as bounded mono PCM WAV for an external ASR service."""

    def __init__(self, config: FfmpegConfig | None = None):
        self.config = config or FfmpegConfig()

    def extract(self, source: StagedMedia, chunk: AudioChunk, *, timeout_seconds: float | None = None) -> PreparedAudioSegment:
        path = source.path
        if not isinstance(path, Path) or not path.is_file() or path.is_symlink():
            raise FfmpegError("media_source_unavailable", "Staged media source is unavailable", 404)
        before = self._digest(path, source.identity)
        input_start_ms = chunk.request_start_ms - chunk.timeline_origin_ms
        duration_seconds = (chunk.request_end_ms - chunk.request_start_ms) / 1000
        command = [self.config.executable, "-nostdin", "-v", "error", "-i", str(path.resolve()),
                   "-ss", f"{input_start_ms / 1000:.3f}", "-t", f"{duration_seconds:.3f}",
                   "-map", f"0:{chunk.stream_index}", "-vn", "-acodec", "pcm_s16le",
                   "-ar", str(self.config.sample_rate), "-ac", str(self.config.channels), "-f", "wav", "pipe:1"]
        try:
            completed = run_bounded(command, timeout_seconds=min(self.config.timeout_seconds,
                                                                 timeout_seconds or self.config.timeout_seconds),
                                    max_output_bytes=self.config.max_output_bytes)
        except BoundedProcessError as error:
            if error.kind == "missing":
                raise FfmpegError("media_tool_missing", "FFmpeg is not installed or not on PATH", 503) from None
            if error.kind == "timeout":
                raise FfmpegError("media_tool_timeout", "FFmpeg exceeded the configured time limit", 504) from None
            if error.kind == "limit":
                raise FfmpegError("media_output_limit", "FFmpeg audio output exceeds the configured limit", 413) from None
            raise FfmpegError("media_tool_unavailable", "FFmpeg could not be started", 503) from None
        if completed.returncode != 0 or not completed.stdout:
            raise FfmpegError("media_extract_failed", "FFmpeg could not extract the requested audio chunk", 422)
        after = self._digest(path, source.identity)
        if before != after:
            raise FfmpegError("media_source_changed", "Media source changed during audio extraction", 409)
        digest = hashlib.sha256(completed.stdout).hexdigest()
        artifact = Artifact(id=f"{source.source_id}:{chunk.id}:wav", role="derived", media_type="audio/wav",
                            sha256=digest, size_bytes=len(completed.stdout))
        return PreparedAudioSegment(source_id=source.source_id, source_sha256=source.source_sha256,
                                    source_artifact_id=source.source_id, stream_index=chunk.stream_index,
                                    start_ms=chunk.request_start_ms, end_ms=chunk.request_end_ms,
                                    artifact=artifact, content=completed.stdout)

    @staticmethod
    def _digest(path: Path, source: MediaProbeInput) -> tuple[int, str]:
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    digest.update(chunk)
        except OSError:
            raise FfmpegError("media_source_unavailable", "Staged media source is unavailable", 404) from None
        value = digest.hexdigest()
        if size != source.size_bytes or value != source.source_sha256:
            raise FfmpegError("media_source_changed", "Media source identity does not match the request", 409)
        return size, value


class MediaTranscriptionResult(Model):
    summary: MediaExecutionSummary
    chunks: list[AudioChunk]
    responses: list[AsrResponse]
    failed_chunk_ids: list[str]


class MediaTranscriptionRunner:
    """Connect probe → FFmpeg chunks → injected external ASR → coverage gate."""

    def __init__(self, extractor: AudioExtractor, provider: AsrProvider,
                 coordinator: MediaInvocationPort | None = None,
                 publish_response=None):
        self.extractor = extractor
        self.provider = provider
        self.coordinator = coordinator
        self.publish_response = publish_response

    def transcribe(self, source: StagedMedia, probe, *, max_segment_ms: int,
                   overlap_ms: int = 0, language: str | None = None,
                   word_timestamps: bool = True, diarization: bool = False,
                   timeout_seconds: float = 300.0,
                   cancelled=lambda: False) -> MediaTranscriptionResult:
        stream_index = require_audio_stream(probe)
        try:
            chunks = plan_audio_chunks(source.source_id, probe, stream_index,
                                       max_segment_ms=max_segment_ms, overlap_ms=overlap_ms)
        except MediaTimelineError:
            raise
        outcomes = []
        usages = []
        responses = []
        failed = []
        seen_segments: set[tuple[str, str | None, int]] = set()
        deadline = time.monotonic() + timeout_seconds
        if self.coordinator is not None:
            fingerprints = [hashlib.sha256(
                f"{source.source_sha256}:{chunk.id}:{chunk.request_start_ms}:{chunk.request_end_ms}:"
                f"{language}:{word_timestamps}:{diarization}".encode("utf-8")
            ).hexdigest() for chunk in chunks]
            self.coordinator.plan([MediaInvocationUnit(unit_id=chunk.id, request_fingerprint=fingerprint)
                                   for chunk, fingerprint in zip(chunks, fingerprints)])
        for chunk in chunks:
            if cancelled() or time.monotonic() >= deadline:
                issue = "media_cancelled" if cancelled() else "media_timeout"
                if self.coordinator is not None and self.coordinator.current(chunk.id).state == "planned":
                    self.coordinator.cancel(chunk.id)
                outcomes.append(MediaChunkOutcome(chunk_id=chunk.id, core_start_ms=chunk.core_start_ms,
                                                  core_end_ms=chunk.core_end_ms, status="failed", issue_code=issue))
                failed.append(chunk.id)
                continue
            try:
                remaining = max(0.1, deadline - time.monotonic())
                segment = self.extractor.extract(source, chunk, timeout_seconds=remaining)
                submitted = self.coordinator.submit(chunk.id) if self.coordinator is not None else None
                request = AsrRequest(segment=segment, language=language, word_timestamps=word_timestamps,
                                     diarization=diarization, timeout_seconds=min(remaining, 300),
                                     trace_id=f"{source.source_id}:{chunk.id}", idempotency_key=chunk.id)
                response = self.provider.transcribe(request)
                if cancelled():
                    raise ProviderError("provider_cancelled_after_send", "Transcription cancelled after sending", retryable=False)
                if self.coordinator is not None:
                    if self.publish_response is None:
                        raise ParseError("media_response_publisher_required", "A response publisher is required for durable media execution", 500)
                    artifact_id = self.publish_response(response, submitted.id)
                    self.coordinator.succeed(
                        chunk.id, artifact_id,
                        ProviderUsage(cost_micros=response.usage.cost_micros),
                        billing_state="known" if response.usage.cost_micros is not None else "unknown",
                    )
                filtered = []
                for item in response.segments:
                    if item.end_ms <= chunk.core_start_ms or item.start_ms >= chunk.core_end_ms:
                        continue
                    key = (item.text.strip().casefold(), item.speaker, item.start_ms)
                    if key in seen_segments:
                        continue
                    seen_segments.add(key)
                    filtered.append(item)
                responses.append(response.model_copy(update={"segments": filtered}))
                outcomes.append(MediaChunkOutcome(chunk_id=chunk.id, core_start_ms=chunk.core_start_ms,
                                                  core_end_ms=chunk.core_end_ms, status="completed"))
                usages.append(response.usage)
            except ProviderError as error:
                if self.coordinator is not None:
                    current = self.coordinator.current(chunk.id)
                    if current.state == "planned":
                        self.coordinator.cancel(chunk.id)
                    elif current.state in {"submitted", "unknown"}:
                        self.coordinator.unknown(chunk.id, error.code)
                outcomes.append(MediaChunkOutcome(chunk_id=chunk.id, core_start_ms=chunk.core_start_ms,
                                                  core_end_ms=chunk.core_end_ms, status="failed", issue_code=error.code))
                failed.append(chunk.id)
                if error.code not in {"provider_invalid_request", "provider_request_limit"}:
                    usages.append(AsrUsage(input_ms=chunk.request_end_ms - chunk.request_start_ms, cost_micros=None))
            except ParseError as error:
                if self.coordinator is not None:
                    current = self.coordinator.current(chunk.id)
                    if current.state == "planned":
                        self.coordinator.cancel(chunk.id)
                    elif current.state in {"submitted", "unknown"}:
                        self.coordinator.unknown(chunk.id, error.code)
                outcomes.append(MediaChunkOutcome(chunk_id=chunk.id, core_start_ms=chunk.core_start_ms,
                                                  core_end_ms=chunk.core_end_ms, status="failed", issue_code=error.code))
                failed.append(chunk.id)
            except Exception:
                if self.coordinator is not None:
                    current = self.coordinator.current(chunk.id)
                    if current.state == "planned":
                        self.coordinator.cancel(chunk.id)
                    elif current.state in {"submitted", "unknown"}:
                        self.coordinator.unknown(chunk.id, "media_execution_unknown")
                outcomes.append(MediaChunkOutcome(chunk_id=chunk.id, core_start_ms=chunk.core_start_ms,
                                                  core_end_ms=chunk.core_end_ms, status="failed", issue_code="media_execution_unknown"))
                failed.append(chunk.id)
        stream = next(item for item in probe.streams if item.index == stream_index)
        timeline_start = stream.start_ms if stream.start_ms is not None else (probe.start_ms or 0)
        summary = summarize_execution("transcribe", timeline_start, timeline_start + probe.duration_ms,
                                      outcomes, usages)
        return MediaTranscriptionResult(summary=summary, chunks=chunks, responses=responses,
                                        failed_chunk_ids=failed)
