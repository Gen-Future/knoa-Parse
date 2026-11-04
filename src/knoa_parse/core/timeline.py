"""Audio chunk and subtitle timeline contracts."""
from typing import Literal

from pydantic import Field, model_validator

from .models import Model


class AudioChunk(Model):
    id: str = Field(min_length=1, max_length=200)
    stream_index: int = Field(ge=0)
    request_start_ms: int
    request_end_ms: int
    core_start_ms: int
    core_end_ms: int
    timeline_origin_ms: int = 0

    @model_validator(mode="after")
    def valid_ranges(self):
        if not (self.request_start_ms < self.request_end_ms and self.core_start_ms < self.core_end_ms
                and self.request_start_ms <= self.core_start_ms < self.core_end_ms <= self.request_end_ms):
            raise ValueError("Audio chunk ranges are inconsistent")
        return self


class SubtitleCue(Model):
    id: str = Field(min_length=1, max_length=200)
    format: Literal["srt", "vtt"]
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=100000)

    @model_validator(mode="after")
    def valid_text_and_range(self):
        if self.end_ms <= self.start_ms or not self.text.strip():
            raise ValueError("Subtitle cue must contain text and a forward range")
        return self


class SubtitleTrack(Model):
    source_id: str = Field(min_length=1)
    language: str | None = Field(default=None, max_length=32)
    format: Literal["srt", "vtt"]
    cues: list[SubtitleCue] = Field(max_length=100000)

    @model_validator(mode="after")
    def ordered_cues(self):
        if any(left.start_ms > right.start_ms for left, right in zip(self.cues, self.cues[1:])):
            raise ValueError("Subtitle cues must be ordered")
        return self
