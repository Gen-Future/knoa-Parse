"""Worker-side assembly for durable media transcription execution.

This is an internal injection point.  Public jobs stay closed until real ASR
acceptance, but any future media worker must use the same Store/coordinator
path instead of calling a provider directly.
"""
from knoa_parse.core.media import MediaProbe
from knoa_parse.core.store import Store
from knoa_parse.enrichment.invocations import InvocationCoordinator
from knoa_parse.processors.media.ffmpeg import (
    AudioExtractor,
    MediaTranscriptionResult,
    MediaTranscriptionRunner,
)
from knoa_parse.processors.media.source import StagedMedia
from knoa_parse.core.asr import AsrProvider


def execute_media_transcription(
    store: Store,
    run_id: str,
    staged: StagedMedia,
    probe: MediaProbe,
    extractor: AudioExtractor,
    provider: AsrProvider,
    publish_response,
    *,
    provider_name: str,
    load_response=None,
    config_fingerprint: str,
    max_attempts: int = 2,
    **options,
) -> MediaTranscriptionResult:
    coordinator = InvocationCoordinator(
        store, run_id, provider_name, "transcribe", config_fingerprint,
        max_attempts=max_attempts,
    )
    runner = MediaTranscriptionRunner(coordinator=coordinator, extractor=extractor,
                                      provider=provider, publish_response=publish_response,
                                      load_response=load_response)
    return runner.transcribe(staged, probe, **options)
