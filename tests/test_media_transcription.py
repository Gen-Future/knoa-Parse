import hashlib
import unittest

from knoa_parse.core.asr import AsrResponse, AsrUsage, TranscriptSegment
from knoa_parse.core.errors import ProviderError
from knoa_parse.core.media import MediaProbe, MediaStream, MediaTimeBase, MediaProbeInput
from knoa_parse.core.models import Artifact
from knoa_parse.processors.media.ffmpeg import MediaTranscriptionRunner
from tests.test_media_timeline import _probe


class _Extractor:
    def __init__(self):
        self.calls = []

    def extract(self, source, chunk):
        self.calls.append(chunk)
        content = f"wav-{chunk.id}".encode()
        return __import__("knoa_parse.core.asr", fromlist=["PreparedAudioSegment"]).PreparedAudioSegment(
            source_id=source.source_id, source_sha256=source.source_sha256, source_artifact_id=source.source_id,
            stream_index=chunk.stream_index, start_ms=chunk.request_start_ms, end_ms=chunk.request_end_ms,
            artifact=Artifact(id=f"artifact-{chunk.id}", role="derived", media_type="audio/wav",
                              sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content)), content=content)


class _Provider:
    def __init__(self):
        self.calls = []

    def describe(self):
        return None

    def transcribe(self, request):
        self.calls.append(request)
        if len(self.calls) == 2:
            raise ProviderError("provider_timeout", "synthetic timeout", retryable=True)
        return AsrResponse(provider="synthetic", model="remote", source_id=request.segment.source_id,
                           stream_index=request.segment.stream_index, segment_start_ms=request.segment.start_ms,
                           segment_end_ms=request.segment.end_ms,
                           segments=[TranscriptSegment(text="片段", start_ms=request.segment.start_ms,
                                                       end_ms=request.segment.start_ms + 100)],
                           usage=AsrUsage(input_ms=request.segment.end_ms - request.segment.start_ms,
                                          cost_micros=None))


class MediaTranscriptionTests(unittest.TestCase):
    def test_runner_preserves_partial_chunks_and_unknown_cost(self):
        source_bytes = b"source"
        source = MediaProbeInput(source_id="source", source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                                 size_bytes=len(source_bytes), path=__import__("pathlib").Path(__file__))
        extractor, provider = _Extractor(), _Provider()
        result = MediaTranscriptionRunner(extractor, provider).transcribe(
            source, _probe(duration=5000), max_segment_ms=3000, overlap_ms=500,
            language="zh-CN", word_timestamps=True, diarization=True)
        self.assertEqual(result.summary.coverage.status, "partial")
        self.assertEqual(result.summary.cost.billing_state, "unknown")
        self.assertIsNone(result.summary.cost.cost_micros)
        self.assertEqual(len(result.responses), 2)
        self.assertEqual(result.failed_chunk_ids, ["audio-1-1"])
        self.assertTrue(all(request.segment.source_id == "source" for request in provider.calls))

    def test_no_audio_is_rejected_before_extractor(self):
        source_bytes = b"source"
        source = MediaProbeInput(source_id="source", source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                                 size_bytes=len(source_bytes), path=__import__("pathlib").Path(__file__))
        extractor = _Extractor()
        with self.assertRaises(Exception) as caught:
            MediaTranscriptionRunner(extractor, _Provider()).transcribe(
                source, _probe(audio=False), max_segment_ms=1000)
        self.assertEqual(caught.exception.code, "media_audio_required")
        self.assertEqual(extractor.calls, [])


if __name__ == "__main__":
    unittest.main()
