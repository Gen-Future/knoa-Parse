"""Optional HTTP transport for the same single-principal store and worker."""
import os
import secrets
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import Field

from knoa_parse.apps.runtime import capabilities, make_store
from knoa_parse.core.errors import ParseError
from knoa_parse.core.models import Model
from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store


class JobRequest(Model):
    source_id: str = Field(min_length=1, max_length=128)
    target: str = Field(default="native_extract", max_length=64)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


def create_app(settings: Settings, token: str) -> FastAPI:
    if not token:
        raise ValueError("A nonempty API token is required")
    store = make_store(settings)

    def authenticate(authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization.encode("utf-8"), ("Bearer " + token).encode("utf-8")):
            raise ParseError("unauthorized", "A valid bearer token is required", 401)

    app = FastAPI(title="Knoa Parse", version="0.1.0.dev0", dependencies=[Depends(authenticate)])

    @app.exception_handler(ParseError)
    async def parse_error(request: Request, exc: ParseError):
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})

    @app.get("/v1/capabilities")
    def get_capabilities():
        return capabilities()

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
    token = os.getenv("KNOA_PARSE_API_TOKEN", "")
    if not token:
        raise RuntimeError("Set KNOA_PARSE_API_TOKEN before starting the API")
    return create_app(Settings(Path(os.getenv("KNOA_PARSE_DATA_DIR", ".local/knoa-parse"))), token)
