"""Single-host task leases and immutable, hash-addressed artifacts."""
import hashlib
import json
import os
import sqlite3
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from .errors import ParseError
from .models import ParseResult, Source
from .probe import probe
from .settings import Settings

class Store:
    def __init__(self, settings: Settings, read_only: bool = False):
        self.settings = settings
        self.root = settings.data_dir.resolve()
        self.read_only = read_only
        if read_only:
            return
        for name in ("blobs", "staging"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs(
                    id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
                    state TEXT NOT NULL, target TEXT NOT NULL,
                    request_key TEXT UNIQUE, token TEXT, lease_until REAL,
                    error TEXT, result_id TEXT, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifacts(
                    id TEXT PRIMARY KEY, digest TEXT NOT NULL, media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS jobs_recent ON jobs(created DESC, id DESC);
            """)

    @contextmanager
    def connection(self):
        path = self.root / "tasks.sqlite3"
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10) if self.read_only else sqlite3.connect(path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def blob_path(self, digest: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ParseError("invalid_digest", "Invalid artifact digest")
        return self.root / "blobs" / digest

    def _publish(self, path: Path, digest: str):
        destination = self.blob_path(digest)
        # Atomic rename only publishes fully written files. Existing bytes are reverified.
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise ParseError("artifact_corrupt", "Stored artifact failed integrity verification", 500)
            path.unlink()
        else:
            os.replace(path, destination)

    def ingest(self, stream: BinaryIO, filename: str) -> Source:
        filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
        if not filename or len(filename) > 255:
            raise ParseError("invalid_filename", "A filename of at most 255 characters is required")
        digest = hashlib.sha256()
        total = 0
        descriptor, name = tempfile.mkstemp(dir=self.root / "staging")
        path = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as out:
                while chunk := stream.read(65536):
                    total += len(chunk)
                    if total > self.settings.max_source_bytes:
                        raise ParseError("resource_limit", "Source exceeds the upload limit", 413)
                    digest.update(chunk)
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            # Windows requires the writer to be closed before reading or publishing.
            media_type = probe(path, filename)
            source = Source(id=uuid.uuid4().hex, revision=digest.hexdigest(), filename=filename,
                            sha256=digest.hexdigest(), size_bytes=total, media_type=media_type)
            self._publish(path, source.sha256)
        finally:
            path.unlink(missing_ok=True)
        with self.connection() as db:
            db.execute("INSERT INTO sources VALUES(?, ?)", (source.id, source.model_dump_json()))
            db.execute("INSERT INTO artifacts VALUES(?, ?, ?, ?)",
                       (source.id, source.sha256, media_type, total))
        return source

    def source(self, source_id: str) -> Source:
        with self.connection() as db:
            row = db.execute("SELECT body FROM sources WHERE id=?", (source_id,)).fetchone()
        if row is None:
            raise ParseError("source_not_found", "Source does not exist", 404)
        return Source.model_validate_json(row["body"])

    def verify_source(self, source: Source) -> Path:
        path = self.blob_path(source.sha256)
        if not path.exists() or path.stat().st_size != source.size_bytes:
            raise ParseError("source_corrupt", "Original source is missing or has changed", 500)
        if hashlib.sha256(path.read_bytes()).hexdigest() != source.sha256:
            raise ParseError("source_corrupt", "Original source digest has changed", 500)
        return path

    def create_job(self, source_id: str, target: str = "native_extract", request_key: str | None = None) -> dict:
        source = self.source(source_id)
        if target != "native_extract":
            raise ParseError("capability_missing", "This target needs an external capability not configured")
        if source.media_type not in self.settings.accepted_media_types:
            raise ParseError("engine_not_enabled", "Document engine has not passed integration acceptance")
        job_id = uuid.uuid4().hex
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if request_key:
                row = db.execute("SELECT * FROM jobs WHERE request_key=?", (request_key,)).fetchone()
                if row:
                    if row["source_id"] != source_id or row["target"] != target:
                        raise ParseError("idempotency_conflict", "Key already belongs to another request", 409)
                    return self._job(row)
            db.execute("INSERT INTO jobs(id,source_id,state,target,request_key,created) VALUES(?,?,'queued',?,?,?)",
                       (job_id, source_id, target, request_key, time.time()))
        return self.job(job_id)

    @staticmethod
    def _job(row) -> dict:
        return {"id": row["id"], "source_id": row["source_id"], "state": row["state"],
                "target": row["target"], "error": json.loads(row["error"]) if row["error"] else None,
                "result_artifact_id": row["result_id"]}

    def job(self, job_id: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise ParseError("job_not_found", "Job does not exist", 404)
        return self._job(row)

    def list_jobs(self, limit: int = 50) -> dict:
        """Bounded recent-task observation; no execution or lease mutation."""
        if not 1 <= limit <= 100:
            raise ParseError("invalid_limit", "Limit must be between 1 and 100", 422)
        with self.connection() as db:
            rows = db.execute(
                "SELECT jobs.*, sources.body AS source_body FROM jobs JOIN sources ON sources.id=jobs.source_id "
                "ORDER BY jobs.created DESC, jobs.id DESC LIMIT ?", (limit + 1,),
            ).fetchall()
        return {"items": [{**self._job(row), "created_at": row["created"],
                           "source": Source.model_validate_json(row["source_body"]).model_dump(mode="json")}
                          for row in rows[:limit]], "has_more": len(rows) > limit, "limit": limit}

    def claim(self, job_id: str | None = None) -> tuple[str, str] | None:
        now = time.time()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE jobs SET state='failed', token=NULL, error=? WHERE state='running' AND lease_until < ?",
                       (json.dumps({"code": "worker_lost", "message": "Execution lease expired; explicit retry required"}), now))
            query = "SELECT id FROM jobs WHERE state='queued'"
            args = ()
            if job_id:
                query += " AND id=?"
                args = (job_id,)
            row = db.execute(query + " ORDER BY created LIMIT 1", args).fetchone()
            if row is None:
                return None
            token = uuid.uuid4().hex
            db.execute("UPDATE jobs SET state='running',token=?,lease_until=? WHERE id=?",
                       (token, now + 2 * self.settings.job_timeout_seconds + 5, row["id"]))
            return row["id"], token

    def cancel(self, job_id: str) -> dict:
        self.job(job_id)
        with self.connection() as db:
            db.execute("UPDATE jobs SET state='cancelled', token=NULL WHERE id=? AND state IN ('queued','running')", (job_id,))
        return self.job(job_id)

    def fail(self, job_id: str, token: str, code: str, message: str):
        with self.connection() as db:
            db.execute("UPDATE jobs SET state='failed',token=NULL,error=? WHERE id=? AND state='running' AND token=?",
                       (json.dumps({"code": code, "message": message}), job_id, token))

    def finish(self, job_id: str, token: str, result: ParseResult, staged: Path | None = None):
        job = self.job(job_id)
        if job["state"] != "running":
            return
        if result.source != self.source(job["source_id"]):
            raise ParseError("source_mismatch", "Result does not belong to this job", 500)
        raw = result.model_dump_json(indent=2).encode("utf-8") + b"\n"
        if len(raw) > self.settings.max_result_bytes:
            raise ParseError("resource_limit", "Result exceeds configured size", 413)
        additions = [a for a in result.artifacts if a.role != "source"]
        if len(raw) + sum(a.size_bytes for a in additions) > self.settings.max_result_bytes:
            raise ParseError("resource_limit", "Result and artifacts exceed the output budget", 413)
        for artifact in additions:
            if staged is None:
                raise ParseError("artifact_missing", "A derived artifact is missing", 500)
            item = staged / artifact.sha256
            if not item.is_file() or item.stat().st_size != artifact.size_bytes or hashlib.sha256(item.read_bytes()).hexdigest() != artifact.sha256:
                raise ParseError("artifact_corrupt", "A staged artifact failed verification", 500)
        for artifact in additions:
            # Multiple references to the same bytes are published once.
            item = staged / artifact.sha256
            if item.exists():
                self._publish(item, artifact.sha256)
        digest = hashlib.sha256(raw).hexdigest()
        artifact_id = "result-" + job_id
        descriptor, name = tempfile.mkstemp(dir=self.root / "staging")
        path = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as out:
                out.write(raw)
                out.flush()
                os.fsync(out.fileno())
            self._publish(path, digest)
        finally:
            path.unlink(missing_ok=True)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute("UPDATE jobs SET state=?,result_id=?,token=NULL WHERE id=? AND state='running' AND token=?",
                                 ({"completed": "succeeded", "partial": "partial", "failed": "failed"}[result.status],
                                  artifact_id, job_id, token)).rowcount
            if changed:
                db.execute("INSERT INTO artifacts VALUES(?, ?, 'application/json', ?)", (artifact_id, digest, len(raw)))
                for artifact in additions:
                    db.execute("INSERT OR IGNORE INTO artifacts VALUES(?, ?, ?, ?)",
                               (artifact.id, artifact.sha256, artifact.media_type, artifact.size_bytes))

    def artifact(self, artifact_id: str) -> tuple[Path, str]:
        with self.connection() as db:
            row = db.execute("SELECT * FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
        if row is None:
            raise ParseError("artifact_not_found", "Artifact does not exist", 404)
        path = self.blob_path(row["digest"])
        if not path.exists() or path.stat().st_size != row["size_bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != row["digest"]:
            raise ParseError("artifact_corrupt", "Stored artifact failed integrity verification", 500)
        return path, row["media_type"]

    def result(self, job_id: str) -> ParseResult:
        artifact_id = self.job(job_id)["result_artifact_id"]
        if not artifact_id:
            raise ParseError("result_not_ready", "No published result for this job", 409)
        path, _ = self.artifact(artifact_id)
        return ParseResult.model_validate_json(path.read_bytes())
