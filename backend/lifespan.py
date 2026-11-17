"""서버 시작 시 AI·경고 모듈을 준비하고 종료 시 참조를 정리한다."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from models.warning_manager.warning_manager import DefaultWarningManager


logger = logging.getLogger(__name__)


def resolve_ai_mode() -> str:
    """명시한 모드를 우선하며, 기존 활성화 설정도 계속 지원한다."""
    mode = os.getenv("PIC_AI_MODE")
    if mode is not None:
        mode = mode.strip()
        if mode not in {"disabled", "development", "checkpoint"}:
            raise ValueError(
                "PIC_AI_MODE는 disabled, development, checkpoint 중 하나여야 합니다."
            )
        return mode

    enabled = os.getenv("PIC_AI_ENABLED", "0").strip()
    if enabled not in {"0", "1"}:
        raise ValueError("PIC_AI_ENABLED는 0 또는 1이어야 합니다.")
    return "checkpoint" if enabled == "1" else "disabled"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.risk_analyzer = None
    app.state.warning_manager = None
    app.state.ai_mode = "disabled"

    try:
        mode = resolve_ai_mode()
        app.state.ai_mode = mode

        # 경고 모듈은 학습된 모델 없이도 사용할 수 있다.
        app.state.warning_manager = DefaultWarningManager()

        if mode == "development":
            # 체크포인트 없이도 기존 어댑터·계산·경고·저장 흐름을 사용한다.
            from backend.services.development_analyzer import load_development_analyzer

            logger.warning(
                "개발용 AI를 준비합니다. 판단층은 미학습 상태이며 점수는 연결 확인용입니다."
            )
            app.state.risk_analyzer = load_development_analyzer()

        elif mode == "checkpoint":
            checkpoint_path = os.getenv("PIC_AI_CHECKPOINT", "").strip()
            model_version = os.getenv("PIC_AI_MODEL_VERSION", "").strip()

            if not checkpoint_path:
                raise ValueError("PIC_AI_CHECKPOINT 설정이 필요합니다.")

            if not model_version:
                raise ValueError("PIC_AI_MODEL_VERSION 설정이 필요합니다.")

            # AI를 사용할 때만 무거운 AI 라이브러리를 불러온다.
            from backend.services.ai_loader import load_risk_analyzer

            app.state.risk_analyzer = load_risk_analyzer(
                checkpoint_path,
                model_version=model_version,
                device="cpu",
            )

        # 여기까지 성공해야 서버가 요청을 받기 시작한다.
        yield

    finally:
        # 서버가 보관하던 객체 참조를 해제한다.
        app.state.risk_analyzer = None
        app.state.warning_manager = None
        app.state.ai_mode = "disabled"
