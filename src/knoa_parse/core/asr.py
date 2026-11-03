"""Supplier-neutral external ASR contracts.

The provider receives one prepared audio segment and returns timestamps already
mapped to the original stream timeline.  It never loads a local speech model.
"""
from typing import Literal, Protocol

from pydantic import Field, model_validator

from .models import Artifact, Model


class PreparedAudioSegment(Model):
    source_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    source_artifact_id: str = Field(min_length=1)
    stream_index: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    artifact: Artifact
    content: bytes = Field(min_length=1, exclude=True, repr=False)

    @model_validator(mode="after")
    def valid_range_and_artifact(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("Audio segment must have a forward time range")
        if self.artifact.role != "derived" or self.artifact.size_bytes != len(self.content):
            raise ValueError("Audio segment artifact does not match its bytes")
        return self


class AsrRequest(Model):
    segment: PreparedAudioSegment
    language: str | None = Field(default=None, max_length=32)
    word_timestamps: bool = False
    diarization: bool = False
    timeout_seconds: float = Field(gt=0, le=300)
    trace_id: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=200)


class TranscriptWord(Model):
    text: str = Field(min_length=1, max_length=10000)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    speaker: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def forward(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("Transcript word must have a forward range")
        return self


class TranscriptSegment(Model):
    text: str = Field(min_length=1, max_length=100000)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    words: list[TranscriptWord] = Field(default_factory=list, max_length=10000)
    speaker: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def valid_content_and_words(self):
        if not self.text.strip() or self.end_ms <= self.start_ms:
            raise ValueError("Transcript segment must contain text and a forward range")
        if any(word.start_ms < self.start_ms or word.end_ms > self.end_ms for word in self.words):
            raise ValueError("Transcript word falls outside its segment")
        return self


class AsrUsage(Model):
    input_ms: int | None = Field(default=None, ge=0)
    cost_micros: int | None = Field(default=None, ge=0)


class AsrResponse(Model):
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    source_id: str = Field(min_length=1)
    stream_index: int = Field(ge=0)
    segment_start_ms: int = Field(ge=0)
    segment_end_ms: int = Field(gt=0)
    language: str | None = Field(default=None, max_length=32)
    segments: list[TranscriptSegment] = Field(max_length=10000)
    usage: AsrUsage

    @model_validator(mode="after")
    def source_range_and_order(self):
        if self.segment_end_ms <= self.segment_start_ms:
            raise ValueError("ASR source range must be forward")
        previous = self.segment_start_ms
        for item in self.segments:
            if item.start_ms < self.segment_start_ms or item.end_ms > self.segment_end_ms:
                raise ValueError("ASR segment falls outside the requested source range")
            if item.start_ms < previous:
                raise ValueError("ASR segments must be ordered")
            previous = item.start_ms
        return self


class AsrCapability(Model):
    provider: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    execution: Literal["external_service", "mock"]
    media_types: list[str] = Field(min_length=1, max_length=20)
    max_segment_bytes: int = Field(gt=0)
    max_segment_ms: int = Field(gt=0)
    word_timestamps: bool
    diarization: bool


class AsrProvider(Protocol):
    def describe(self) -> AsrCapability: ...

    def transcribe(self, request: AsrRequest) -> AsrResponse: ...
