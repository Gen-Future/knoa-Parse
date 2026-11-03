"""M4 media coverage and cost gates."""
from collections.abc import Iterable

from knoa_parse.core.asr import AsrUsage
from knoa_parse.core.errors import ParseError
from knoa_parse.core.media import MediaProbe
from knoa_parse.core.media_results import (
    MediaChunkOutcome,
    MediaCostSummary,
    MediaCoverage,
    MediaExecutionSummary,
)


class MediaCoverageError(ParseError):
    """Sanitized error for media target preflight and summaries."""


def require_audio_stream(probe: MediaProbe) -> int:
    for stream in probe.streams:
        if stream.kind == "audio":
            return stream.index
    raise MediaCoverageError("media_audio_required", "The requested media target requires an audio stream", 422)


def summarize_execution(target: str, requested_start_ms: int, requested_end_ms: int,
                        outcomes: Iterable[MediaChunkOutcome], usages: Iterable[AsrUsage]) -> MediaExecutionSummary:
    if target not in {"transcribe", "video_understanding"}:
        raise MediaCoverageError("media_invalid_target", "Unsupported media target", 422)
    if requested_start_ms < 0 or requested_end_ms <= requested_start_ms:
        raise MediaCoverageError("media_invalid_range", "Requested media range is invalid", 422)
    outcome_list = list(outcomes)
    if len({outcome.chunk_id for outcome in outcome_list}) != len(outcome_list):
        raise MediaCoverageError("media_duplicate_chunk", "Media chunk outcomes must be unique", 422)
    for left, right in zip(sorted(outcome_list, key=lambda item: item.core_start_ms),
                           sorted(outcome_list, key=lambda item: item.core_start_ms)[1:]):
        if left.core_end_ms > right.core_start_ms:
            raise MediaCoverageError("media_overlap", "Media chunk core ranges must not overlap", 422)
    completed = sorted((outcome for outcome in outcome_list if outcome.status == "completed"),
                       key=lambda item: item.core_start_ms)
    failed = sorted((outcome for outcome in outcome_list if outcome.status == "failed"),
                    key=lambda item: item.core_start_ms)
    covered = _union_ranges([(item.core_start_ms, item.core_end_ms) for item in completed])
    missing = _subtract_ranges(requested_start_ms, requested_end_ms,
                               [(item.core_start_ms, item.core_end_ms) for item in completed])
    requested = requested_end_ms - requested_start_ms
    if not outcome_list or not completed:
        status = "failed"
    elif failed or missing or covered != requested:
        status = "partial"
    else:
        status = "completed"
    coverage = MediaCoverage(requested_start_ms=requested_start_ms, requested_end_ms=requested_end_ms,
                             covered_ms=covered, missing_ranges=[[start, end] for start, end in missing],
                             status=status)
    usage_list = list(usages)
    if len(usage_list) > len(outcome_list):
        raise MediaCoverageError("media_usage_conflict", "Usage observations exceed media chunks", 422)
    if not usage_list:
        cost = MediaCostSummary(billing_state="not_sent", cost_micros=None, observed_chunks=0)
    elif any(usage.cost_micros is None for usage in usage_list):
        cost = MediaCostSummary(billing_state="unknown", cost_micros=None, observed_chunks=len(usage_list))
    else:
        cost = MediaCostSummary(billing_state="known", cost_micros=sum(usage.cost_micros for usage in usage_list),
                                observed_chunks=len(usage_list))
    return MediaExecutionSummary(target=target, coverage=coverage, cost=cost)


def _union_ranges(ranges: list[tuple[int, int]]) -> int:
    if not ranges:
        return 0
    ordered = sorted(ranges)
    start, end = ordered[0]
    total = 0
    for next_start, next_end in ordered[1:]:
        if next_start > end:
            total += end - start
            start, end = next_start, next_end
        else:
            end = max(end, next_end)
    return total + end - start


def _subtract_ranges(start: int, end: int, covered: list[tuple[int, int]]) -> list[tuple[int, int]]:
    missing = []
    cursor = start
    for covered_start, covered_end in sorted(covered):
        if covered_end <= start or covered_start >= end:
            continue
        covered_start, covered_end = max(start, covered_start), min(end, covered_end)
        if covered_start > cursor:
            missing.append((cursor, covered_start))
        cursor = max(cursor, covered_end)
    if cursor < end:
        missing.append((cursor, end))
    return missing
