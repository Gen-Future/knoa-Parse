import hashlib
import tempfile
import unittest
from pathlib import Path

from knoa_parse.apps.worker.media_execution import execute_media_transcription
from knoa_parse.core.media import MediaProbeInput
from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store
from knoa_parse.processors.media.source import StagedMedia
from tests.test_media_timeline import _probe
from tests.test_media_transcription import _Extractor, _Provider


class MediaWorkerAssemblyTests(unittest.TestCase):
    def test_worker_assembly_uses_store_and_coordinator(self):
        raw = b"source"
        with tempfile.TemporaryDirectory() as directory:
            staged_path = Path(directory) / "source.bin"
            staged_path.write_bytes(raw)
            staged = StagedMedia(MediaProbeInput(source_id="source", source_sha256=hashlib.sha256(raw).hexdigest(),
                                                 size_bytes=len(raw)), staged_path)
            store = Store(Settings(Path(directory) / "data"))
            provider = _Provider()
            result = execute_media_transcription(
                store, "worker-run", staged, _probe(duration=1000), _Extractor(), provider,
                lambda response, invocation_id: f"artifact-{invocation_id}",
                provider_name="synthetic", config_fingerprint="c" * 64, max_segment_ms=1000,
            )
            records = store.list_invocations("worker-run")
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].state, "succeeded")
            self.assertEqual(result.summary.coverage.status, "completed")


if __name__ == "__main__":
    unittest.main()
