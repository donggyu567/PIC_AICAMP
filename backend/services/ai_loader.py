"""학습된 체크포인트를 불러와 서버용 AI 분석기를 생성한다."""
from pathlib import Path

from backend.services.koelectra_analyzer import KoElectraRiskAnalyzer
from risk_speech_ai.checkpoint import (
    read_checkpoint,
    validate_checkpoint_metadata
)
from risk_speech_ai.inference import (
    ThresholdConfig,
    load_checkpoint_inference
)
from risk_speech_ai.tokenization import load_koelectra_tokenizer

def load_risk_analyzer(
        checkpoint_path: str | Path,
        *,
        model_version: str,
        thresholds: ThresholdConfig | None = None,
        device: str = "cpu"
) -> KoElectraRiskAnalyzer:
    if (
        not isinstance(model_version, str)
        or not model_version.strip()
        or len(model_version) > 120
    ):
        raise ValueError("model_version은 1~120자의 문자열이어야 합니다.")

    path = Path(checkpoint_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"체크포인트 파일이 없습니다: {path}")

    checkpoint = read_checkpoint(path)
    metadata = validate_checkpoint_metadata(checkpoint)

    tokenizer_revision = (
        metadata["resolved_tokenizer_revision"]
        or metadata["requested_tokenizer_revision"]
    )

    tokenizer = load_koelectra_tokenizer(
        revision=tokenizer_revision
    )

    predictor = load_checkpoint_inference(
        path,
        tokenizer=tokenizer,
        thresholds=thresholds,
        device=device,
        checkpoint=checkpoint,
    )

    return KoElectraRiskAnalyzer(
        predictor,
        model_version=model_version
    )
