"""Bounded FFmpeg subtitle-stream extraction into SRT/WebVTT cues."""
import hashlib
from dataclasses import dataclass
from pathlib import Path

from knoa_parse.core.errors import ParseError
from knoa_parse.core.media import MediaProbe
from knoa_parse.core.timeline import SubtitleTrack

from .process import BoundedProcessError, run_bounded
from .source import StagedMedia
from .timeline import MediaTimelineError, parse_subtitle_track


class SubtitleExtractionError(ParseError):
    """Sanitized error from media-container subtitle extraction."""


@dataclass(frozen=True)
class SubtitleExtractorConfig:
    executable: str = "ffmpeg"
    executable_args: tuple[str, ...] = ()
    timeout_seconds: float = 60.0
    max_output_bytes: int = 20 * 1024 * 1024

    def __post_init__(self):
        if not isinstance(self.executable, str) or not self.executable.strip() \
                or any(ord(c) < 32 for c in self.executable):
            raise ValueError("Invalid FFmpeg executable")
        if not isinstance(self.executable_args, tuple) or any(
                not isinstance(arg, str) or not arg or any(ord(c) < 32 for c in arg)
                for arg in self.executable_args):
            raise ValueError("Invalid FFmpeg executable arguments")
        if type(self.timeout_seconds) not in {int, float} or not 0.1 <= self.timeout_seconds <= 600:
            raise ValueError("Subtitle extraction timeout is outside the allowed range")
        if type(self.max_output_bytes) is not int or not 1024 <= self.max_output_bytes <= 128 * 1024 * 1024:
            raise ValueError("Subtitle output limit is outside the allowed range")


class FfmpegSubtitleExtractor:
    def __init__(self, config: SubtitleExtractorConfig | None = None):
        self.config = config or SubtitleExtractorConfig()

    def extract(self, source: StagedMedia, probe: MediaProbe, stream_index: int,
                *, language: str | None = None) -> SubtitleTrack:
        stream = next((item for item in probe.streams if item.index == stream_index), None)
        if stream is None or stream.kind != "subtitle":
            raise SubtitleExtractionError("subtitle_stream_missing", "Requested subtitle stream is unavailable", 422)
        path = source.path
        before = self._digest(path, source)
        command = [self.config.executable, *self.config.executable_args, "-nostdin", "-v", "error", "-i", str(path.resolve()),
                   "-map", f"0:{stream_index}", "-f", "webvtt", "pipe:1"]
        try:
            completed = run_bounded(command, timeout_seconds=self.config.timeout_seconds,
                                    max_output_bytes=self.config.max_output_bytes)
        except BoundedProcessError as error:
            code = {"missing": "media_tool_missing", "timeout": "media_tool_timeout",
                    "limit": "subtitle_output_limit"}.get(error.kind, "media_tool_unavailable")
            status = 413 if error.kind == "limit" else 504 if error.kind == "timeout" else 503
            raise SubtitleExtractionError(code, "Subtitle extraction process failed", status) from None
        if completed.returncode != 0 or not completed.stdout:
            raise SubtitleExtractionError("subtitle_extract_failed", "FFmpeg could not extract subtitle stream", 422)
        after = self._digest(path, source)
        if before != after:
            raise SubtitleExtractionError("media_source_changed", "Media source changed during subtitle extraction", 409)
        try:
            text = completed.stdout.decode("utf-8")
        except UnicodeDecodeError:
            raise SubtitleExtractionError("subtitle_encoding_invalid", "Subtitle stream is not UTF-8 WebVTT", 422) from None
        try:
            return parse_subtitle_track(source.source_id, text, format="vtt", language=language)
        except MediaTimelineError as error:
            raise SubtitleExtractionError(error.code, error.message, error.status_code) from None

    @staticmethod
    def _digest(path: Path, source: StagedMedia) -> tuple[int, str]:
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    size += len(chunk)
                    digest.update(chunk)
        except OSError:
            raise SubtitleExtractionError("media_source_unavailable", "Staged media source is unavailable", 404) from None
        value = digest.hexdigest()
        if size != source.size_bytes or value != source.source_sha256:
            raise SubtitleExtractionError("media_source_changed", "Media source identity does not match the request", 409)
        return size, value
