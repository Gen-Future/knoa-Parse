"""Non-model audio segmentation and SRT/WebVTT parsing."""
import re

from knoa_parse.core.errors import ParseError
from knoa_parse.core.media import MediaProbe
from knoa_parse.core.timeline import AudioChunk, SubtitleCue, SubtitleTrack


class MediaTimelineError(ParseError):
    """Sanitized error for invalid media timeline input."""


def plan_audio_chunks(source_id: str, probe: MediaProbe, stream_index: int, *,
                      max_segment_ms: int, overlap_ms: int = 0) -> list[AudioChunk]:
    if not source_id or type(stream_index) is not int or stream_index < 0:
        raise MediaTimelineError("media_invalid_request", "Invalid audio stream request", 422)
    if type(max_segment_ms) is not int or not 1 <= max_segment_ms <= 24 * 60 * 60 * 1000:
        raise MediaTimelineError("media_invalid_request", "Invalid audio segment limit", 422)
    if type(overlap_ms) is not int or not 0 <= overlap_ms * 2 < max_segment_ms:
        raise MediaTimelineError("media_invalid_request", "Invalid audio overlap", 422)
    stream = next((item for item in probe.streams if item.index == stream_index), None)
    if stream is None or stream.kind != "audio":
        raise MediaTimelineError("media_audio_stream_missing", "Requested audio stream is unavailable", 422)
    if probe.duration_ms is None or probe.duration_ms <= 0:
        raise MediaTimelineError("media_duration_missing", "A finite media duration is required", 422)
    # Keep both the previous and next boundary context while staying within
    # the provider's maximum request duration.
    step = max_segment_ms - 2 * overlap_ms
    chunks = []
    core_start = 0
    ordinal = 0
    while core_start < probe.duration_ms:
        core_end = min(probe.duration_ms, core_start + step)
        request_start = max(0, core_start - overlap_ms)
        request_end = min(probe.duration_ms, core_end + overlap_ms)
        chunks.append(AudioChunk(id=f"audio-{stream_index}-{ordinal}", stream_index=stream_index,
                                 request_start_ms=request_start, request_end_ms=request_end,
                                 core_start_ms=core_start, core_end_ms=core_end))
        core_start = core_end
        ordinal += 1
    return chunks


_TIME = re.compile(r"^(?:(\d+):)?(\d{1,2}):([0-5]\d)[,.](\d{3})$")


def parse_subtitle_track(source_id: str, text: str, *, format: str, language: str | None = None) -> SubtitleTrack:
    if format not in {"srt", "vtt"} or not isinstance(text, str) or len(text) > 20_000_000:
        raise MediaTimelineError("subtitle_invalid_request", "Invalid subtitle input", 422)
    lines = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if format == "vtt":
        if not lines or lines[0].strip().upper() != "WEBVTT":
            raise MediaTimelineError("subtitle_invalid_header", "WebVTT header is required", 422)
        lines = lines[1:]
    cues = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        cue_id = lines[index].strip()
        if "-->" in cue_id:
            timing = cue_id
            cue_id = f"cue-{len(cues)}"
        else:
            index += 1
            if index >= len(lines):
                raise MediaTimelineError("subtitle_invalid_timing", "Subtitle timing is missing", 422)
            timing = lines[index].strip()
        if "-->" not in timing:
            raise MediaTimelineError("subtitle_invalid_timing", "Subtitle timing is invalid", 422)
        left, right = [part.strip() for part in timing.split("-->", 1)]
        right = right.split()[0]
        start, end = _parse_timestamp(left), _parse_timestamp(right)
        index += 1
        text_lines = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index])
            index += 1
        cue_text = "\n".join(text_lines).strip()
        if not cue_text or end <= start:
            raise MediaTimelineError("subtitle_invalid_cue", "Subtitle cue is empty or not forward", 422)
        cues.append(SubtitleCue(id=cue_id, format=format, start_ms=start, end_ms=end, text=cue_text))
    try:
        return SubtitleTrack(source_id=source_id, language=language, format=format, cues=cues)
    except ValueError:
        raise MediaTimelineError("subtitle_invalid_cue", "Subtitle cue validation failed", 422) from None


def _parse_timestamp(value: str) -> int:
    match = _TIME.fullmatch(value)
    if not match:
        raise MediaTimelineError("subtitle_invalid_timestamp", "Subtitle timestamp is invalid", 422)
    hours = int(match.group(1) or 0)
    minutes, seconds, millis = int(match.group(2)), int(match.group(3)), int(match.group(4))
    if minutes > 59:
        raise MediaTimelineError("subtitle_invalid_timestamp", "Subtitle timestamp is invalid", 422)
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis
