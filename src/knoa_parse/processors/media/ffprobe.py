"""Controlled ffprobe adapter; no codec or machine-learning code is bundled."""
import hashlib
import json
import math
import subprocess
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from knoa_parse.core.errors import ParseError
from knoa_parse.core.media import (
    MediaFrame,
    MediaProbe,
    MediaProbeInput,
    MediaRate,
    MediaStream,
    MediaTimeBase,
)


class MediaProbeError(ParseError):
    """Sanitized error from the external ffprobe process or its output."""


@dataclass(frozen=True)
class FfprobeConfig:
    executable: str = "ffprobe"
    executable_args: tuple[str, ...] = ()
    timeout_seconds: float = 30.0
    max_output_bytes: int = 16 * 1024 * 1024
    max_streams: int = 256
    max_frames: int = 200_000

    def __post_init__(self):
        if not isinstance(self.executable, str) or not self.executable.strip() \
                or any(ord(c) < 32 for c in self.executable):
            raise ValueError("Invalid ffprobe executable")
        if not isinstance(self.executable_args, tuple) or any(
            not isinstance(arg, str) or not arg or any(ord(c) < 32 for c in arg)
            for arg in self.executable_args
        ):
            raise ValueError("Invalid ffprobe executable arguments")
        if type(self.timeout_seconds) not in {int, float} or not math.isfinite(self.timeout_seconds) \
                or not 0.1 <= self.timeout_seconds <= 300:
            raise ValueError("ffprobe timeout is outside the allowed range")
        for value, minimum, maximum in (
            (self.max_output_bytes, 1024, 128 * 1024 * 1024),
            (self.max_streams, 1, 256),
            (self.max_frames, 1, 200_000),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError("ffprobe resource limit is outside the allowed range")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Nonstandard JSON number")


def _integer(value, *, required: bool = False) -> int | None:
    if value is None or value == "":
        if required:
            raise ValueError("Missing integer")
        return None
    if isinstance(value, bool):
        raise ValueError("Boolean is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    raise ValueError("Invalid integer")


def _decimal(value, *, required: bool = False) -> Decimal | None:
    if value is None or value == "":
        if required:
            raise ValueError("Missing decimal")
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid decimal") from None
    if not result.is_finite():
        raise ValueError("Non-finite decimal")
    return result


def _milliseconds(value, *, allow_negative: bool = True) -> int | None:
    number = _decimal(value)
    if number is None:
        return None
    if not allow_negative and number < 0:
        raise ValueError("Negative duration")
    return int((number * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _ratio(value) -> MediaRate | None:
    if value is None or value == "" or value == "0/0":
        return None
    if not isinstance(value, str) or value.count("/") != 1:
        raise ValueError("Invalid rate")
    numerator, denominator = value.split("/")
    numerator_i, denominator_i = _integer(numerator, required=True), _integer(denominator, required=True)
    if numerator_i <= 0 or denominator_i <= 0:
        return None
    return MediaRate(numerator=numerator_i, denominator=denominator_i)


class FfprobeMediaProber:
    """Run ffprobe with a fixed JSON command and verify the source identity."""

    def __init__(self, config: FfprobeConfig | None = None):
        self.config = config or FfprobeConfig()

    def probe(self, source: MediaProbeInput, *, include_frames: bool = False,
              stream_index: int | None = None) -> MediaProbe:
        if include_frames and stream_index is not None and (type(stream_index) is not int or stream_index < 0):
            raise MediaProbeError("media_invalid_request", "Invalid media stream selector", 422)
        path = source.path
        # The path is excluded from serialized source identity and must be
        # attached by a trusted staging boundary before this process call.
        if not isinstance(path, Path) or not path.is_file() or path.is_symlink():
            raise MediaProbeError("media_source_unavailable", "Staged media source is unavailable", 404)
        before = self._digest(path, source)
        command = [self.config.executable, *self.config.executable_args,
                   "-v", "error", "-print_format", "json", "-show_format", "-show_streams"]
        if include_frames:
            if stream_index is not None:
                command.extend(["-select_streams", f"{stream_index}"])
            command.extend(["-show_frames", "-show_entries",
                            "frame=stream_index,best_effort_timestamp,pkt_duration,key_frame"])
        command.append(str(path.resolve()))
        try:
            completed = subprocess.run(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                shell=False, timeout=min(self.config.timeout_seconds, 300), check=False,
            )
        except FileNotFoundError:
            raise MediaProbeError("media_tool_missing", "ffprobe is not installed or not on PATH", 503) from None
        except subprocess.TimeoutExpired:
            raise MediaProbeError("media_tool_timeout", "ffprobe exceeded the configured time limit", 504) from None
        except OSError:
            raise MediaProbeError("media_tool_unavailable", "ffprobe could not be started", 503) from None
        if len(completed.stdout) > self.config.max_output_bytes:
            raise MediaProbeError("media_probe_limit", "ffprobe output exceeds the configured limit", 413)
        if completed.returncode != 0:
            raise MediaProbeError("media_probe_failed", "ffprobe rejected the media source", 422)
        try:
            payload = json.loads(completed.stdout.decode("utf-8"), object_pairs_hook=_unique_object,
                                 parse_constant=_reject_constant)
            result = self._parse_payload(payload, source, include_frames=include_frames)
        except (UnicodeDecodeError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
            raise MediaProbeError("media_probe_invalid_response", "ffprobe returned invalid media metadata", 422) from None
        after = self._digest(path, source)
        if before != after:
            raise MediaProbeError("media_source_changed", "Media source changed during probing", 409)
        return result

    def _digest(self, path: Path, source: MediaProbeInput) -> tuple[int, str]:
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
            raise MediaProbeError("media_source_unavailable", "Staged media source is unavailable", 404) from None
        if size != source.size_bytes or digest.hexdigest() != source.source_sha256:
            raise MediaProbeError("media_source_changed", "Media source identity does not match the request", 409)
        return size, digest.hexdigest()

    def _parse_payload(self, payload: Any, source: MediaProbeInput, *, include_frames: bool) -> MediaProbe:
        if not isinstance(payload, dict) or not isinstance(payload.get("format"), dict):
            raise ValueError("Missing ffprobe format")
        raw_streams = payload.get("streams")
        if not isinstance(raw_streams, list) or not raw_streams or len(raw_streams) > self.config.max_streams:
            raise ValueError("Invalid ffprobe streams")
        streams = []
        for raw in raw_streams:
            if not isinstance(raw, dict):
                raise ValueError("Invalid stream")
            # Data/attachment streams are not inputs for audio/video dispatch;
            # skip them rather than inventing a time base.
            if raw.get("codec_type") not in {"audio", "video", "subtitle"}:
                continue
            streams.append(self._parse_stream(raw))
        if not streams:
            raise ValueError("No supported media streams")
        frames = self._parse_frames(payload.get("frames", []), streams) if include_frames else []
        raw_format = payload["format"]
        format_name = raw_format.get("format_name")
        if not isinstance(format_name, str) or not format_name.strip() or len(format_name) > 300:
            raise ValueError("Invalid format name")
        return MediaProbe(
            source_id=source.source_id, source_sha256=source.source_sha256, size_bytes=source.size_bytes,
            format_name=format_name, start_ms=_milliseconds(raw_format.get("start_time")),
            duration_ms=_milliseconds(raw_format.get("duration"), allow_negative=False),
            streams=streams, frames=frames,
        )

    def _parse_stream(self, raw: Any) -> MediaStream:
        if not isinstance(raw, dict):
            raise ValueError("Invalid stream")
        index = _integer(raw.get("index"), required=True)
        codec_type = raw.get("codec_type")
        kind = codec_type if codec_type in {"audio", "video", "subtitle"} else "other"
        time_base = raw.get("time_base")
        if not isinstance(time_base, str) or time_base.count("/") != 1:
            raise ValueError("Missing stream time base")
        tb_num, tb_den = (_integer(item, required=True) for item in time_base.split("/"))
        if tb_num <= 0 or tb_den <= 0:
            raise ValueError("Invalid stream time base")
        width = _integer(raw.get("width"))
        height = _integer(raw.get("height"))
        sample_rate = _integer(raw.get("sample_rate"))
        channels = _integer(raw.get("channels"))
        return MediaStream(
            index=index, kind=kind, codec_name=raw.get("codec_name") if isinstance(raw.get("codec_name"), str) else None,
            time_base=MediaTimeBase(numerator=tb_num, denominator=tb_den),
            start_pts=_integer(raw.get("start_pts")), duration_ts=_integer(raw.get("duration_ts")),
            start_ms=_milliseconds(raw.get("start_time")), duration_ms=_milliseconds(raw.get("duration"), allow_negative=False),
            width=width, height=height, sample_rate=sample_rate, channels=channels,
            frame_rate=_ratio(raw.get("r_frame_rate")), average_frame_rate=_ratio(raw.get("avg_frame_rate")),
            frame_count=_integer(raw.get("nb_frames")),
        )

    def _parse_frames(self, raw_frames: Any, streams: list[MediaStream]) -> list[MediaFrame]:
        if not isinstance(raw_frames, list) or len(raw_frames) > self.config.max_frames:
            raise ValueError("Invalid ffprobe frames")
        known = {stream.index: stream.time_base for stream in streams}
        frames = []
        for raw in raw_frames:
            if not isinstance(raw, dict):
                raise ValueError("Invalid frame")
            stream_index = _integer(raw.get("stream_index"), required=True)
            pts = _integer(raw.get("best_effort_timestamp"), required=True)
            if stream_index not in known:
                raise ValueError("Frame references unknown stream")
            time_base = known[stream_index]
            pts_ms = int((Decimal(pts * time_base.numerator) * Decimal(1000) / Decimal(time_base.denominator)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP))
            key_frame = raw.get("key_frame")
            if key_frame is not None and type(key_frame) not in {int, bool}:
                raise ValueError("Invalid key frame flag")
            frames.append(MediaFrame(stream_index=stream_index, pts=pts, pts_ms=pts_ms,
                                     duration_ts=_integer(raw.get("pkt_duration")),
                                     key_frame=bool(key_frame) if key_frame is not None else None))
        return frames
