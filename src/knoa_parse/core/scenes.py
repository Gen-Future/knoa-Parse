"""Engine-independent video scene and timeline association contracts."""
from typing import Literal

from pydantic import Field, model_validator

from .models import Model


class TimeRange(Model):
    start_ms: int
    end_ms: int

    @model_validator(mode="after")
    def forward(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("Time range must be forward")
        return self


class SceneSample(Model):
    frame_index: int = Field(ge=0)
    pts_ms: int
    duration_ms: int = Field(gt=0)
    change_score: float = Field(ge=0, le=1)


class Scene(Model):
    id: str = Field(min_length=1, max_length=100)
    stream_index: int = Field(ge=0)
    start_ms: int
    end_ms: int
    start_frame_index: int = Field(ge=0)
    end_frame_index: int = Field(ge=0)
    sampled_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def valid_scene(self):
        if self.end_ms <= self.start_ms or self.end_frame_index < self.start_frame_index:
            raise ValueError("Scene must have forward time and frame ranges")
        if self.sampled_ms > self.end_ms - self.start_ms:
            raise ValueError("Scene sample coverage exceeds scene duration")
        return self


class SceneCoverage(Model):
    requested: TimeRange
    sampled_ranges: list[TimeRange] = Field(default_factory=list, max_length=10000)
    sample_count: int = Field(ge=0)
    covered_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def covered(self):
        if self.covered_ms > self.requested.end_ms - self.requested.start_ms:
            raise ValueError("Sample coverage exceeds requested timeline")
        if any(item.start_ms < self.requested.start_ms or item.end_ms > self.requested.end_ms
               for item in self.sampled_ranges):
            raise ValueError("Sample range falls outside requested timeline")
        return self


class SceneDetectionResult(Model):
    source_id: str = Field(min_length=1)
    stream_index: int = Field(ge=0)
    scenes: list[Scene] = Field(max_length=10000)
    coverage: SceneCoverage
    detector: str = Field(min_length=1, max_length=100)


class SceneEvidence(Model):
    id: str = Field(min_length=1, max_length=200)
    source_id: str = Field(min_length=1)
    kind: Literal["transcript", "subtitle", "audio"]
    start_ms: int
    end_ms: int
    stream_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def forward(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("Evidence range must be forward")
        return self


class SceneEvidenceLink(Model):
    scene_id: str
    evidence_ids: list[str] = Field(default_factory=list)
