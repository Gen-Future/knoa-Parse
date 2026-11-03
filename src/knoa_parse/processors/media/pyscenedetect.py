"""Optional PySceneDetect 0.7 adapter with conservative timestamp mapping."""
import hashlib
import importlib
import math
from dataclasses import dataclass
from pathlib import Path

from knoa_parse.core.errors import ParseError
from knoa_parse.core.media import MediaProbeInput
from knoa_parse.core.scenes import Scene, SceneCoverage, SceneDetectionResult, TimeRange


class PySceneDetectError(ParseError):
    """Sanitized error from the optional scene detector."""


@dataclass(frozen=True)
class PySceneDetectConfig:
    detector: str = "adaptive"
    backend: str = "opencv"
    adaptive_threshold: float = 3.0
    content_threshold: float = 27.0
    min_scene_len_frames: int = 15
    max_scenes: int = 10000

    def __post_init__(self):
        if self.detector not in {"adaptive", "content"}:
            raise ValueError("Unsupported PySceneDetect detector")
        if self.backend not in {"opencv"}:
            raise ValueError("Only the audited OpenCV backend is enabled")
        for value in (self.adaptive_threshold, self.content_threshold):
            if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
                raise ValueError("PySceneDetect threshold must be positive")
        if type(self.min_scene_len_frames) is not int or not 1 <= self.min_scene_len_frames <= 100000:
            raise ValueError("PySceneDetect minimum scene length is outside the allowed range")
        if type(self.max_scenes) is not int or not 1 <= self.max_scenes <= 100000:
            raise ValueError("PySceneDetect scene limit is outside the allowed range")


class PySceneDetectAdapter:
    """Run the selected non-model detector and map FrameTimecode to ms."""

    def __init__(self, config: PySceneDetectConfig | None = None):
        self.config = config or PySceneDetectConfig()

    def detect(self, source: MediaProbeInput, *, duration_ms: int, stream_index: int = 0) -> SceneDetectionResult:
        if type(duration_ms) is not int or duration_ms <= 0 or type(stream_index) is not int or stream_index < 0:
            raise PySceneDetectError("scene_invalid_request", "A finite video duration and stream are required", 422)
        path = source.path
        if not isinstance(path, Path) or not path.is_file() or path.is_symlink():
            raise PySceneDetectError("scene_source_unavailable", "Staged video source is unavailable", 404)
        before = self._digest(path, source)
        try:
            module = importlib.import_module("scenedetect")
            detector_type = module.AdaptiveDetector if self.config.detector == "adaptive" else module.ContentDetector
            if self.config.detector == "adaptive":
                detector = detector_type(adaptive_threshold=self.config.adaptive_threshold,
                                         min_scene_len=self.config.min_scene_len_frames)
            else:
                detector = detector_type(threshold=self.config.content_threshold,
                                         min_scene_len=self.config.min_scene_len_frames)
            scenes = module.detect(str(path.resolve()), detector, show_progress=False,
                                   start_in_scene=True, backend=self.config.backend)
        except ModuleNotFoundError:
            raise PySceneDetectError("scene_dependency_missing", "PySceneDetect video extra is not installed", 503) from None
        except (ValueError, TypeError):
            raise PySceneDetectError("scene_invalid_configuration", "PySceneDetect rejected the configured detector", 422) from None
        except Exception:
            raise PySceneDetectError("scene_decode_failed", "PySceneDetect could not decode the video", 422) from None
        after = self._digest(path, source)
        if before != after:
            raise PySceneDetectError("media_source_changed", "Video source changed during scene detection", 409)
        if not isinstance(scenes, list) or len(scenes) > self.config.max_scenes:
            raise PySceneDetectError("scene_result_limit", "PySceneDetect returned too many scenes", 413)
        requested = TimeRange(start_ms=0, end_ms=duration_ms)
        result_scenes = []
        total_frames = 0
        for number, pair in enumerate(scenes, start=1):
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise PySceneDetectError("scene_invalid_response", "PySceneDetect returned invalid scene data", 422)
            start_time, end_time = pair
            try:
                start_ms = round(self._seconds(start_time) * 1000)
                end_ms = round(self._seconds(end_time) * 1000)
                start_frame = self._frame_num(start_time)
                end_frame = self._frame_num(end_time)
            except (AttributeError, TypeError, ValueError, OverflowError):
                raise PySceneDetectError("scene_invalid_response", "PySceneDetect returned invalid timestamps", 422) from None
            if start_ms < 0 or end_ms <= start_ms or start_ms > duration_ms or end_ms > duration_ms + 100:
                raise PySceneDetectError("scene_invalid_response", "PySceneDetect timestamp is outside the source", 422)
            end_ms = min(duration_ms, end_ms)
            if start_frame < 0 or end_frame < start_frame:
                raise PySceneDetectError("scene_invalid_response", "PySceneDetect frame range is invalid", 422)
            total_frames += max(0, end_frame - start_frame)
            result_scenes.append(Scene(id=f"scene-{number}", stream_index=stream_index,
                                       start_ms=start_ms, end_ms=end_ms,
                                       start_frame_index=start_frame, end_frame_index=end_frame,
                                       sampled_ms=end_ms - start_ms))
        if not result_scenes:
            raise PySceneDetectError("scene_empty_result", "PySceneDetect produced no scene timeline", 422)
        return SceneDetectionResult(source_id=source.source_id, stream_index=stream_index,
                                    scenes=result_scenes,
                                    coverage=SceneCoverage(requested=requested,
                                                           sampled_ranges=[requested],
                                                           sample_count=total_frames,
                                                           covered_ms=duration_ms),
                                    detector=f"pyscenedetect-{self.config.detector}-{getattr(module, '__version__', '0.7')}")

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
            raise PySceneDetectError("scene_source_unavailable", "Staged video source is unavailable", 404) from None
        value = digest.hexdigest()
        if size != source.size_bytes or value != source.source_sha256:
            raise PySceneDetectError("media_source_changed", "Video source identity does not match the request", 409)
        return size, value

    @staticmethod
    def _seconds(timecode) -> float:
        value = getattr(timecode, "seconds", None)
        if value is not None and not callable(value):
            return float(value)
        return float(timecode.get_seconds())

    @staticmethod
    def _frame_num(timecode) -> int:
        value = getattr(timecode, "frame_num", None)
        if value is not None and not callable(value):
            return int(value)
        return int(timecode.get_frames())
