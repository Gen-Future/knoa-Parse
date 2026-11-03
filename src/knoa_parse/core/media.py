"""Engine-independent media probe contracts.

The models preserve the facts needed to build audio/video timelines without
assuming a fixed frame rate.  A concrete FFmpeg/ffprobe runner lives in the
media processor layer and is injected by an application.
"""
from typing import Literal, Protocol
from pathlib import Path

from pydantic import Field, model_validator

from .models import Model


class MediaProbeInput(Model):
    source_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    path: Path = Field(exclude=True, repr=False)


class MediaRate(Model):
    numerator: int = Field(gt=0)
    denominator: int = Field(gt=0)


class MediaTimeBase(Model):
    numerator: int = Field(gt=0)
    denominator: int = Field(gt=0)


class MediaFrame(Model):
    stream_index: int = Field(ge=0)
    pts: int
    pts_ms: int
    duration_ts: int | None = None
    key_frame: bool | None = None


class MediaStream(Model):
    index: int = Field(ge=0)
    kind: Literal["audio", "video", "subtitle", "other"]
    codec_name: str | None = None
    time_base: MediaTimeBase
    start_pts: int | None = None
    duration_ts: int | None = None
    start_ms: int | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    sample_rate: int | None = Field(default=None, gt=0)
    channels: int | None = Field(default=None, gt=0)
    frame_rate: MediaRate | None = None
    average_frame_rate: MediaRate | None = None
    frame_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def kind_shape(self):
        if self.kind == "video" and (self.width is None or self.height is None):
            raise ValueError("Video stream dimensions are required")
        if self.kind == "audio" and (self.sample_rate is None or self.channels is None):
            raise ValueError("Audio stream sample rate and channels are required")
        return self


class MediaProbe(Model):
    source_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    format_name: str = Field(min_length=1, max_length=300)
    start_ms: int | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    streams: list[MediaStream] = Field(min_length=1, max_length=256)
    frames: list[MediaFrame] = Field(default_factory=list, max_length=200_000)

    @model_validator(mode="after")
    def unique_streams_and_frames(self):
        stream_ids = [stream.index for stream in self.streams]
        if len(stream_ids) != len(set(stream_ids)):
            raise ValueError("Media stream indexes must be unique")
        for frame in self.frames:
            if frame.stream_index not in set(stream_ids):
                raise ValueError("Frame references an unknown stream")
        return self


class MediaProber(Protocol):
    def probe(self, source: MediaProbeInput, *, include_frames: bool = False,
              stream_index: int | None = None) -> MediaProbe: ...
