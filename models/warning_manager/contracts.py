"""공통 입출력. AI 점수는 0~1, 계산 결과·외부 표시 점수는 0~100.
타입은 형태만 정의한다. 값 검증은 구현체, 중복·저장·정정 재생 관리는 서버 책임이다.
"""

from dataclasses import dataclass
from typing import Literal, TypedDict

RiskType = Literal[
    "institution_impersonation", "money_transfer", "personal_information",
    "app_installation", "secrecy", "threat_pressure", "loan_fraud", "information_probing",
]
WarningStatus = Literal["none", "active", "previous_warning"]
WarningReason = Literal["single_utterance", "cumulative", "both"]


class TypeSignals(TypedDict):
    """8개 필수 유형 점수. 각각 0~1."""

    institution_impersonation: float
    money_transfer: float
    personal_information: float
    app_installation: float
    secrecy: float
    threat_pressure: float
    loan_fraud: float
    information_probing: float


@dataclass(frozen=True, kw_only=True)
class ModelRiskResult:
    """error이면 점수·유형 세 필드는 None. ok의 감지 유형 없음은 ()."""

    conversation_id: str
    utterance_id: int
    revision: int
    sequence: int  # 통화 내 발생 순서
    analysis_status: Literal["ok", "error"]
    tuned_text: str  # 분석한 마스킹·보정 문장
    is_phishing_score: float | None  # 0~1
    type_scores: TypeSignals | None
    detected_types: tuple[RiskType, ...] | None
    model_version: str


@dataclass(frozen=True, kw_only=True)
class WindowUtterance:
    """서버가 계산한 발화별 기여 내역. utterance는 반드시 성공 결과."""

    utterance: ModelRiskResult
    weight: float
    effective_risk: float  # d_i, 0~1
    contribution: float  # weight * effective_risk, 0~1


@dataclass(frozen=True, kw_only=True)
class CalculationResult:
    """반올림 전 계산 결과. 창은 발생 순서이며 마지막 항목이 현재 발화다."""

    conversation_id: str
    utterance_id: int
    revision: int
    cumulative_score: float  # 100 * max(M_t, A_t)
    window_max_score: float  # 100 * M_t
    accumulated_score: float  # 100 * A_t
    window_utterances: tuple[WindowUtterance, ...]
    policy_version: str
    window_size: int  # 서버가 실제 적용한 설정(현재 20)
    rho: float
    b: float


@dataclass(frozen=True, kw_only=True)
class WarningConfig:
    """초기 개발 설정. 같은 통화의 순차 처리 동안 고정한다."""

    evidence_threshold: float = 50.0
    warning_threshold: float = 70.0
    representative_evidence_count: int = 3
    warning_policy_version: str = "warning-v1"


class EvidenceItem(TypedDict):
    utterance_id: int
    text: str
    risk_score: float  # 외부 표시 점수 0~100
    risk_types: list[RiskType]


class CumulativeEventPayload(TypedDict):
    trigger_utterance_id: int
    risk_score: float  # 최초 누적 경고 시점의 점수
    utterances: list[EvidenceItem]


class WarningPayload(TypedDict):
    status: WarningStatus
    reason: WarningReason | None
    message: str


class EvidencePayload(TypedDict):
    recent: EvidenceItem | None
    highest: EvidenceItem | None
    cumulative_events: list[CumulativeEventPayload]


class WarningResult(TypedDict):
    warning: WarningPayload
    evidence: EvidencePayload


@dataclass(frozen=True, kw_only=True)
class WarningDecision:
    """정책 판단 결과. 이벤트 생성·종료는 근거·이력 갱신 단계에서 처리한다."""

    status: WarningStatus
    reason: WarningReason | None


@dataclass(frozen=True, kw_only=True)
class WarningEvent:
    """한 번의 연속 경고 구간. reason은 마지막 유효 사유, utterances는 누적 근거 합집합."""

    event_id: str
    initial_calculation: CalculationResult  # 최초 경고 기록
    reason: WarningReason
    peak_score: float  # 최고 누적 점수 0~100
    last_sequence: int
    first_cumulative: CalculationResult | None = None  # 누적 조건 최초 충족 기록
    utterances: tuple[ModelRiskResult, ...] = ()
    closed_sequence: int | None = None  # None이면 활성 이벤트


@dataclass(frozen=True, kw_only=True)
class ConversationWarningState:
    """서버 저장용 상태. 개별·누적 근거를 합쳐 recent/highest를 구한다.
    근거는 성공 결과이며 각 목록에서 (발화 ID, revision)별 유일하다.
    events는 발생 순서이며 활성 이벤트는 마지막 항목이다.
    """

    conversation_id: str
    config: WarningConfig
    status: WarningStatus = "none"
    cumulative_score: float | None = None  # 마지막 성공 누적값 0~100
    individual_evidence: tuple[ModelRiskResult, ...] = ()
    events: tuple[WarningEvent, ...] = ()


@dataclass(frozen=True, kw_only=True)
class WarningUpdate:
    """result는 외부 JSON, state는 저장용. 첫 분석 실패의 state는 None.
    notify_event_id는 서버 내부 알림 요청이며 None이면 요청 없음.
    """

    result: WarningResult
    state: ConversationWarningState | None
    notify_event_id: str | None = None
