"""Optional HTTP transport for the same single-principal store and worker."""
import secrets
import tempfile

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import Field, ValidationError
from starlette.concurrency import run_in_threadpool

from knoa_parse.apps.runtime import capabilities, make_store
from knoa_parse.core.errors import ParseError
from knoa_parse.core.models import Model
from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store
from knoa_parse.core.text_model import ProviderError, TextModelProvider, TextRequest, TextResponse
from knoa_parse.apps.model_services import require_text_provider, text_provider_from_env
from knoa_parse.apps.configuration import server_configuration
from knoa_parse.apps.model_settings import ModelSettingsManager, ModelSettingsRequest


class JobRequest(Model):
    source_id: str = Field(min_length=1, max_length=128)
    target: str = Field(default="native_extract", max_length=64)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


def create_app(settings: Settings, token: str | None = None, text_provider: TextModelProvider | None = None,
               model_settings: ModelSettingsManager | None = None) -> FastAPI:
    store = make_store(settings)

    def authenticate(authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization.encode("utf-8"), ("Bearer " + token).encode("utf-8")):
            raise ParseError("unauthorized", "A valid bearer token is required", 401)

    # The single-user demo is open by default. Explicit library callers can still inject a token.
    app = FastAPI(title="Knoa Parse", version="0.1.0.dev0", dependencies=[Depends(authenticate)] if token else [])

    def current_provider():
        return model_settings.provider if model_settings is not None else text_provider

    def require_model_settings():
        if model_settings is None:
            raise ParseError("settings_unavailable", "Model settings are not managed by this instance", 503)
        return model_settings

    @app.exception_handler(ParseError)
    async def parse_error(request: Request, exc: ParseError):
        error = {"code": exc.code, "message": exc.message}
        if isinstance(exc, ProviderError):
            error["retryable"] = exc.retryable
        return JSONResponse(status_code=exc.status_code, content={"error": error})

    @app.get("/v1/capabilities")
    def get_capabilities():
        return capabilities(current_provider())

    @app.get("/v1/settings/model")
    def get_model_settings():
        return require_model_settings().describe()

    @app.put("/v1/settings/model")
    async def save_model_settings(request: Request):
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 16384:
                raise ParseError("resource_limit", "Model settings exceed body limit", 413)
            body.extend(chunk)
        try:
            changes = ModelSettingsRequest.model_validate_json(bytes(body))
        except ValidationError:
            # Do not echo Pydantic input values, which may contain a new API key.
            raise ParseError("invalid_model_settings", "Invalid model settings fields or values") from None
        return await run_in_threadpool(require_model_settings().update, changes)

    @app.post("/v1/settings/model/test")
    def test_model_settings():
        result = require_text_provider(current_provider()).complete(TextRequest(prompt="Reply with exactly OK.", max_tokens=16))
        return result.model_dump(mode="json")

    @app.post("/v1/models/text", response_model=TextResponse, openapi_extra={
        "requestBody": {"required": True, "content": {"application/json": {"schema": TextRequest.model_json_schema()}}},
    })
    async def generate_text(request: Request):
        provider = require_text_provider(current_provider())
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 192 * 1024:
                raise ParseError("resource_limit", "Model request exceeds body limit", 413)
            body.extend(chunk)
        try:
            work = TextRequest.model_validate_json(bytes(body))
        except ValidationError:
            raise ParseError("invalid_model_request", "Expected prompt, optional system and max_tokens within limits") from None
        response = await run_in_threadpool(provider.complete, work)
        return response.model_dump(mode="json")

    @app.post("/v1/sources", status_code=201)
    async def upload(request: Request, filename: str):
        # Raw binary body avoids a multipart spool accepting an unbounded file before validation.
        with tempfile.TemporaryFile(dir=store.root / "staging") as stream:
            total = 0
            async for chunk in request.stream():
                total += len(chunk)
                if total > settings.max_source_bytes:
                    raise ParseError("resource_limit", "Source exceeds the upload limit", 413)
                stream.write(chunk)
            stream.seek(0)
            return store.ingest(stream, filename).model_dump(mode="json")

    @app.post("/v1/jobs", status_code=202)
    def submit(body: JobRequest):
        return store.create_job(body.source_id, body.target, body.idempotency_key)

    @app.get("/v1/jobs")
    def recent_jobs(limit: int = Query(default=50, ge=1, le=100)):
        return store.list_jobs(limit)

    @app.get("/v1/sources/{source_id}")
    def source_metadata(source_id: str):
        return store.source(source_id).model_dump(mode="json")

    @app.get("/v1/jobs/{job_id}")
    def status(job_id: str):
        return store.job(job_id)

    @app.post("/v1/jobs/{job_id}/cancel")
    def cancel(job_id: str):
        return store.cancel(job_id)

    @app.get("/v1/jobs/{job_id}/result")
    def result(job_id: str):
        return store.result(job_id).model_dump(mode="json")

    @app.get("/v1/artifacts/{artifact_id}")
    def artifact(artifact_id: str):
        path, media_type = store.artifact(artifact_id)
        return FileResponse(path, media_type=media_type)

    return app


def create_from_env() -> FastAPI:
    settings = server_configuration()
    import os
    from pathlib import Path

    provider = text_provider_from_env()
    manager = ModelSettingsManager(Path(os.getenv("KNOA_PARSE_PROVIDER_CONFIG", ".local/providers.json")), provider,
                                   editable=not any(name.startswith("KNOA_PARSE_MODEL_") for name in os.environ))
    return create_app(settings, text_provider=provider, model_settings=manager)
