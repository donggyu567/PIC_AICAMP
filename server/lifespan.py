"""기존 AI 수명 관리와 새 서버의 공유 OpenAI 클라이언트를 묶는다."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.lifespan import lifespan as backend_lifespan
from server.analysis.context_service import create_llm_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with backend_lifespan(app):
        client = create_llm_client()
        app.state.llm_client = client
        try:
            yield
        finally:
            app.state.llm_client = None
            if client is not None:
                client.close()
