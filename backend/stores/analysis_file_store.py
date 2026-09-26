"""통화별 입력·응답·정책을 하나의 JSON 파일로 저장한다.

읽기-계산-쓰기 전체는 서비스의 Lock으로 보호한다. 단일 worker 전용이다.
"""

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator
)
from backend.schemas import CalculationPreviewResponse, ModelResultRequest
from backend.stores.analysis_store import AnalysisStore
from models.warning_manager.contracts import (
    ConversationWarningState, ModelRiskResult, WarningConfig,
)


class AnalysisStorageError(RuntimeError):
    """파일 읽기·쓰기 또는 저장 형식 검증에 실패한 경우."""


class CalculationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    window_size: int = Field(ge=1)
    rho: float = Field(gt=0, le=1, allow_inf_nan=False)
    b: float = Field(ge=0, lt=1, allow_inf_nan=False)
    policy_version: str = Field(min_length=1)


class AnalysisAttempt(BaseModel):
    """한 번의 분석 시도에 대한 입력과 응답."""

    model_config = ConfigDict(extra="forbid", strict=True)

    model_result: ModelResultRequest
    response: CalculationPreviewResponse

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        current = self.model_result.to_model_result()
        response = self.response
        for field in (
            "conversation_id", "utterance_id", "revision", "sequence",
            "analysis_status",
        ):
            if getattr(current, field) != getattr(response, field):
                raise ValueError("저장된 입력과 응답의 식별 정보가 다릅니다.")
        if response.current_text != current.tuned_text:
            raise ValueError("저장된 입력과 응답의 문장이 다릅니다.")
        if current.analysis_status == "error":
            if any(getattr(response, field) is not None for field in (
                "current_risk_score", "cumulative_risk_score", "type_scores",
                "detected_types", "calculation",
            )):
                raise ValueError("실패 응답에 계산 결과가 포함되어 있습니다.")
        else:
            if response.calculation is None or response.cumulative_risk_score is None:
                raise ValueError("성공 응답에 계산 결과가 없습니다.")
            if response.current_risk_score != 100.0 * current.is_phishing_score:
                raise ValueError("입력 점수와 응답 점수가 다릅니다.")
            expected_types = {
                name: 100.0 * score for name, score in current.type_scores.items()
            }
            if (
                response.type_scores != expected_types
                or response.detected_types != list(current.detected_types)
            ):
                raise ValueError("입력 유형과 응답 유형이 다릅니다.")
        return self


class StoredAnalysis(AnalysisAttempt):
    """현재 유효한 결과와 시간 순서대로 보존한 이전 실패 시도."""

    previous_attempts: list[AnalysisAttempt] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_previous_attempts(self) -> Self:
        for attempt in self.previous_attempts:
            if attempt.model_result.analysis_status != "error":
                raise ValueError("재시도 이력에는 이전 실패 결과만 보존할 수 있습니다.")
            for field in (
                "conversation_id", "utterance_id", "revision", "sequence", "tuned_text",
            ):
                if getattr(attempt.model_result, field) != getattr(self.model_result, field):
                    raise ValueError("재시도 이력이 현재 발화와 일치하지 않습니다.")
        return self


class ConversationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    storage_version: Literal["1.0"] = "1.0"
    conversation_id: str = Field(min_length=1, max_length=120)

    conversation_status: Literal["active", "ended"] = "active"
    ended_at: AwareDatetime | None = None

    policy: CalculationPolicy
    records: list[StoredAnalysis] = Field(min_length=1)
    warning_config: WarningConfig | None = None
    warning_state: ConversationWarningState | None = None
    pending_notification_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.conversation_status == "active":
            if self.ended_at is not None:
                raise ValueError(
                    "진행 중인 통화에는 종료 시각이 없어야 합니다."
                )
        elif self.ended_at is None:
            raise ValueError(
                "종료된 통화에는 종료 시각이 필요합니다."
            )
        return self

    @model_validator(mode="after")
    def validate_records(self) -> Self:
        if self.warning_config is None:
            if self.warning_state is not None or self.pending_notification_ids:
                raise ValueError("경고 미연결 통화에 경고 상태나 알림이 있습니다.")
        elif self.warning_state is not None:
            if (
                self.warning_state.conversation_id != self.conversation_id
                or self.warning_state.config != self.warning_config
            ):
                raise ValueError("저장된 경고 상태의 통화·설정이 다릅니다.")
        if (
            any(not event_id.strip() for event_id in self.pending_notification_ids)
            or len(self.pending_notification_ids) != len(set(self.pending_notification_ids))
        ):
            raise ValueError("알림 대기 ID가 비어 있거나 중복되었습니다.")
        history = AnalysisStore()
        for index, record in enumerate(self.records):
            current = record.model_result.to_model_result()
            response = record.response
            if (self.warning_config is None) != (response.warning is None):
                raise ValueError("통화의 경고 연동 여부와 응답이 다릅니다.")
            if current.conversation_id != self.conversation_id:
                raise ValueError("저장 파일에 다른 통화가 포함되어 있습니다.")
            history.add(current)
            if current.analysis_status == "error":
                if index != len(self.records) - 1:
                    raise ValueError("실패 발화 뒤에 후속 결과가 저장되어 있습니다.")
            else:
                for field, value in self.policy.model_dump().items():
                    if getattr(response.calculation, field) != value:
                        raise ValueError("응답 계산 설정과 통화 정책이 다릅니다.")
        if self.warning_config is not None:
            if any(record.model_result.analysis_status == "ok" for record in self.records):
                if self.warning_state is None:
                    raise ValueError("성공 분석이 있는 통화의 경고 상태가 없습니다.")
            if self.warning_state is not None:
                if self.records[-1].response.warning["status"] != self.warning_state.status:
                    raise ValueError("마지막 응답과 경고 저장 상태가 다릅니다.")
        return self


class AnalysisFileStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()

    def path_for(self, conversation_id: str) -> Path:
        # 통화 ID의 경로 문자나 Windows 예약어를 파일명으로 사용하지 않는다.
        digest = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    def load(self, conversation_id: str) -> ConversationSnapshot | None:
        try:
            text = self.path_for(conversation_id).read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeError) as error:
            raise AnalysisStorageError("분석 기록을 읽을 수 없습니다.") from error

        try:
            snapshot = ConversationSnapshot.model_validate_json(text)
            if snapshot.conversation_id != conversation_id:
                raise ValueError("요청한 통화와 저장된 통화가 다릅니다.")
            return snapshot
        except ValueError as error:
            raise AnalysisStorageError("분석 기록의 형식이 올바르지 않습니다.") from error

    def save(self, snapshot: ConversationSnapshot) -> None:
        temporary_path = None
        try:
            serialized = snapshot.model_dump_json(indent=2)
            self.root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.root,
                prefix=".analysis-", suffix=".tmp", delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(serialized)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path_for(snapshot.conversation_id))
        except (OSError, ValueError) as error:
            raise AnalysisStorageError("분석 기록을 저장할 수 없습니다.") from error
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    # 정리 실패가 실제 저장 성공/실패 결과를 바꾸지 않게 한다.
                    pass

    def get_history(self, conversation_id: str) -> list[ModelRiskResult]:
        snapshot = self.load(conversation_id)
        if snapshot is None:
            return []
        return [item.model_result.to_model_result() for item in snapshot.records]
