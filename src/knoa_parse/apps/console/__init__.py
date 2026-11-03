"""Optional same-origin console shell; the API/worker remain independently runnable."""
from pathlib import Path


def create_app(api):
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'none'"
            )
        return response

    app.mount("/api", api)
    app.mount("/", StaticFiles(directory=Path(__file__).with_name("static"), html=True), name="console")
    return app


def create_from_env():
    from knoa_parse.apps.api import create_from_env as create_api

    return create_app(create_api())
