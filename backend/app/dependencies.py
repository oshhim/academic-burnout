import secrets

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader

from app.facial.service import fail

key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def authenticate(request: Request, key: str | None = Depends(key_header)):
    if key is None or not secrets.compare_digest(key, request.app.state.settings.api_key):
        fail(401, "invalid_api_key", "Supply the configured X-API-Key header.")


def get_db(request: Request):
    with request.app.state.sessions() as session:
        yield session
