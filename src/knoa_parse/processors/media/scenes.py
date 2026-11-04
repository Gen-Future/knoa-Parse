"""Non-model scene candidate detection and timeline association."""
from dataclasses import dataclass

from knoa_parse.core.scenes import (
    Scene,
    SceneDetectionResult,
    SceneEvidence,
    SceneEvidenceLink,
    SceneSample,
    SceneCoverage,
    TimeRange,
)
from knoa_parse.core.errors import ParseError


class SceneDetectionError(ParseError):
    """Sanitized error for invalid sampled video timeline data."""


@dataclass(frozen=True)
class SceneDetectorConfig:
    threshold: float = 0.4
    min_scene_ms: int = 250
    max_samples: int = 200_000

    def __post_init__(self):
        if type(self.threshold) not in {int, float} or not 0 <= self.threshold <= 1:
            raise ValueError("Scene threshold must be within [0,1]")
        if type(self.min_scene_ms) is not int or not 1 <= self.min_scene_ms <= 24 * 60 * 60 * 1000:
            raise ValueError("Scene minimum duration is outside the allowed range")
        if type(self.max_samples) is not int or not 1 <= self.max_samples <= 200_000:
            raise ValueError("Scene sample limit is outside the allowed range")


def detect_scene_candidates(source_id: str, stream_index: int, timeline: TimeRange,
                            samples: list[SceneSample], *, config: SceneDetectorConfig | None = None,
                            detector: str = "rule-change-score-v1") -> SceneDetectionResult:
    """Build scene candidates from actual sample PTS and change scores.

    Pixel comparison belongs to an injected detector such as PySceneDetect;
    this function only applies threshold/min-duration rules and preserves the
    supplied PTS, so it is safe to test without a decoder or model.
    """
    config = config or SceneDetectorConfig()
    if not source_id or stream_index < 0 or len(samples) > config.max_samples:
        raise SceneDetectionError("scene_invalid_request", "Invalid scene detection request", 422)
    ordered = sorted(samples, key=lambda sample: (sample.pts_ms, sample.frame_index))
    if ordered != samples or len({sample.frame_index for sample in samples}) != len(samples):
        raise SceneDetectionError("scene_invalid_timeline", "Scene samples must be ordered and unique", 422)
    if any(sample.pts_ms < timeline.start_ms or sample.pts_ms + sample.duration_ms > timeline.end_ms for sample in samples):
        raise SceneDetectionError("scene_invalid_timeline", "Scene sample is outside the requested timeline", 422)
    ranges = [TimeRange(start_ms=sample.pts_ms, end_ms=min(timeline.end_ms, sample.pts_ms + sample.duration_ms)) for sample in samples]
    covered = _union_duration(ranges)
    boundaries = [timeline.start_ms]
    for sample in samples[1:]:
        if sample.change_score >= config.threshold and sample.pts_ms - boundaries[-1] >= config.min_scene_ms:
            boundaries.append(sample.pts_ms)
    boundaries.append(timeline.end_ms)
    scenes = []
    for number, (start, end) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        in_scene = [sample for sample in samples if start <= sample.pts_ms < end]
        if not in_scene:
            # A gap remains explicit; it is not a fabricated frame or text.
            first_frame = last_frame = 0
            sampled_ms = 0
        else:
            first_frame, last_frame = in_scene[0].frame_index, in_scene[-1].frame_index
            sampled_ms = _union_duration([TimeRange(start_ms=max(start, sample.pts_ms),
                                                     end_ms=min(end, sample.pts_ms + sample.duration_ms))
                                          for sample in in_scene])
        scenes.append(Scene(id=f"scene-{number}", stream_index=stream_index, start_ms=start, end_ms=end,
                            start_frame_index=first_frame, end_frame_index=last_frame, sampled_ms=sampled_ms))
    return SceneDetectionResult(source_id=source_id, stream_index=stream_index, scenes=scenes,
                                coverage=SceneCoverage(requested=timeline, sampled_ranges=ranges,
                                                       sample_count=len(samples), covered_ms=covered),
                                detector=detector)


def associate_scene_evidence(scenes: list[Scene], evidence: list[SceneEvidence], *,
                             source_id: str | None = None) -> list[SceneEvidenceLink]:
    """Link only overlapping source-time intervals; do not infer missing evidence."""
    if len({scene.id for scene in scenes}) != len(scenes) or len({item.id for item in evidence}) != len(evidence):
        raise SceneDetectionError("scene_duplicate_id", "Scene and evidence IDs must be unique", 422)
    links = []
    for scene in scenes:
        ids = [item.id for item in evidence
               if (source_id is None or item.source_id == source_id)
               and (item.stream_index is None or item.stream_index == scene.stream_index)
               and max(scene.start_ms, item.start_ms) < min(scene.end_ms, item.end_ms)]
        links.append(SceneEvidenceLink(scene_id=scene.id, evidence_ids=ids))
    return links


def _union_duration(ranges: list[TimeRange]) -> int:
    if not ranges:
        return 0
    ordered = sorted(ranges, key=lambda item: (item.start_ms, item.end_ms))
    start, end = ordered[0].start_ms, ordered[0].end_ms
    total = 0
    for item in ordered[1:]:
        if item.start_ms > end:
            total += end - start
            start, end = item.start_ms, item.end_ms
        else:
            end = max(end, item.end_ms)
    return total + end - start
