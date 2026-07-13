from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from .cloud_run import CloudRunJobService
from .config import Settings
from .security import verify_admin_token


app = FastAPI(
    title="todaysingi Cloud Worker Dispatcher",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class DispatchRequest(BaseModel):
    reason: str = Field(default="admin_queue", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


async def get_admin(
    authorization: str = Header(default=""),
    settings: Settings = Depends(get_settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer 인증이 필요합니다")
    return await verify_admin_token(token, settings, http_client)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.post("/v1/dispatch", status_code=status.HTTP_202_ACCEPTED)
async def dispatch(
    _request: DispatchRequest,
    _admin=Depends(get_admin),
    settings: Settings = Depends(get_settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),
):
    return await CloudRunJobService(settings, http_client).run()
