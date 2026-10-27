# KoELECTRA 위험감지 v1 체크포인트 인계

기준: [공식 업무 2 문서](https://docs.google.com/document/d/1o_hLBCRA4s_KM-VmcfmEK4K8f_6tObveSnt__AQtlxA/edit?usp=drivesdk), 2026-10-27 로컬·원격 확인. **모델 재학습이나 체크포인트 내용 변경은 하지 않았다.**

## 파일과 전달 상태

| 항목 | 확인 결과 |
| --- | --- |
| 원본 | `artifacts/risk_speech_ai/koelectra_risk_v1.pt` (보존) |
| 서버 전달용 로컬 복사본 | `checkpoints/risk_speech_v1.pt` |
| 두 파일 크기 | 각각 1,348,308,730 bytes |
| 두 파일 SHA-256 | `1131f9dcc665f79073d98ecd6845573109a89e44dbf2917d299a8fea057020a7` (일치) |
| Git 상태 | `/checkpoints/`와 `*.pt`가 `.gitignore` 대상. PR #35에 두 `.pt` 및 LFS 객체가 없음. |
| 외부 공유 | 미실행. 학습 사용 승인과 공개·외부 공유 권한은 구분된다. 허용 수신자, 접근 범위, 공유 링크의 권한이 확인되면 공식 문서의 별도 링크 방식으로 전달해야 한다. |

복사본을 받는 서버 담당자는 배치 후 SHA-256과 크기를 먼저 비교한다. 파일명은 서버 설정에서 지정할 수 있으나 이 인계의 기준 경로는 `checkpoints/risk_speech_v1.pt`다. 현재 AI 학습 CLI의 `CHECKPOINT_PATH`는 원본 `artifacts/risk_speech_ai/koelectra_risk_v1.pt`를 가리키며, 이번 인계 복사는 그 설정과 기존 학습·평가 결과를 바꾸지 않는다.

## schema와 버전

복사본에서 `validate_checkpoint_metadata()`를 통과했다. 필수 최상위 키 `checkpoint_schema_version="v1"`, `model_state_dict`, `optimizer_state_dict`, `training_config`, `label_order`, `base_model`, `metadata`가 모두 존재한다. optimizer 상태는 201개 파라미터 항목을 포함한다. 추론은 optimizer를 실행하지 않지만 현재 schema 검사에는 그 키가 필요하다.

- 기반 모델: `monologg/koelectra-base-v3-discriminator`; 모델 revision `68b30cd259f34a4b5aa8786392612ba2a2617fcc`.
- tokenizer: 동일 모델의 요청 revision `68b30cd259f34a4b5aa8786392612ba2a2617fcc`; checkpoint의 `resolved_tokenizer_revision`은 기록되지 않았고, loader는 요청 revision과 tokenizer fingerprint·동작을 검증한다.
- artifact 식별: `koelectra_risk_v1.pt`, checkpoint schema v1. 공식 문서의 `risk-speech-v1.0`은 **예시 모델 버전 문자열**이다. 실제 백엔드 `model_version` 값은 서버 담당자와 합의해 고정해야 하며 checkpoint에 별도 배포 버전 값으로 저장돼 있지 않다.
- 학습 데이터 버전: `risk-speech-team_lead_training_use_20261026_27-8faa6a7eebfe`; 원자료 Git commit `8faa6a7eebfe95c7ac7fe6c6077a49ebf31f958f`.
- 학습 당시 HEAD: `76e16c02db5491aa33a55c4a92f532ba069a7c58`. 당시 미커밋 학습 코드의 정확한 snapshot은 **not_recorded**이므로 이 commit만으로 학습 코드를 완전히 재현한다고 주장하지 않는다. 인계 문서를 포함하는 PR #35의 코드 commit은 별도로 확인한다.
- 실제 학습: CPU, 1 epoch, batch size 8, learning rate 2e-5, seed 42, AdamW 183 optimizer steps, 1,460발화. 평균 total/risk/type loss `0.870836 / 0.562352 / 0.308484`. CLI 기본 3 epoch와 실제 1 epoch는 다르다.
- 기록된 학습 환경: Python `3.11.16`, PyTorch `2.6.0+cpu`, Transformers `4.57.6`.
- 8개 유형 순서: `institution_impersonation`, `money_transfer`, `personal_information`, `app_installation`, `secrecy`, `threat_pressure`, `loan_fraud`, `information_probing`.

## 서버 로딩 계약과 현재 구현 차이

실제로 존재하고 복사본에서 검증한 AI 모듈 로더는 `risk_speech_ai.inference.load_checkpoint_inference()`다. tokenizer는 `risk_speech_ai.tokenization.load_koelectra_tokenizer()`로 먼저 구성한다.

```python
from risk_speech_ai.inference import InferenceInput, load_checkpoint_inference
from risk_speech_ai.tokenization import load_koelectra_tokenizer

revision = "68b30cd259f34a4b5aa8786392612ba2a2617fcc"
tokenizer = load_koelectra_tokenizer(revision)
session = load_checkpoint_inference(
    "checkpoints/risk_speech_v1.pt", tokenizer=tokenizer, device="cpu"
)
result = session.predict([
    InferenceInput(history_texts=["안녕하세요. 어디세요?"],
                   current_text="검찰청입니다. 안전계좌로 돈을 이체하세요.")
])[0]
```

`result.risk_score`와 `result.type_scores`는 표시용 0~100, `risk_probability`와 `type_probabilities`는 0~1이다. 실제 백엔드 `RiskModelScores`에는 `is_phishing_score=result.risk_probability`, `type_scores=result.type_probabilities`, `detected_types=result.detected_types`를 전달한다. 추가 sigmoid나 100배 변환을 적용하지 않는다. `RiskModelInput`은 현재 보정 문장과 오래된 순서의 이전 최대 5개 보정 문장이다.

**문서와 저장소의 충돌:** 원격 `feature/backend_AiCheckpoint`는 `4502ffa9bdb2039b529d338f5d51f155d041aae2`에 존재하지만 `backend/services/ai_loader.py`와 `load_risk_analyzer()`는 그 브랜치에 없다. 로컬 현재 checkout에도 `backend/` 자체가 없다. 해당 원격 브랜치의 `backend/services/ai_service.py`에는 `RiskAnalyzer` Protocol과 `RiskModelScores`만 있고, `backend/main.py:get_risk_analyzer()`는 서버 시작 시 `app.state.risk_analyzer`에 등록된 구현체를 가져온다. 미등록이면 503을 반환한다. 백엔드 문서도 실제 구현체 로더가 아직 없다고 기록한다. 그러므로 AI loader의 단독 재로딩·추론은 검증됐지만, 공식 업무 문서가 요구한 `load_risk_analyzer()` 호출과 서버의 누적 계산·경고·저장·JSON 응답까지의 **실제 인수 테스트는 아직 불가능**하다. 서버 담당자의 어댑터 및 app.state 등록 작업이 남아 있다. 백엔드 코드는 이번 작업에서 수정하지 않았다.

## 실제 복사본 추론 예시

위의 합성 한국어 문맥 1개와 현재 발화 1개에 대해 CPU에서 `checkpoints/risk_speech_v1.pt`를 재로딩해 측정했다. 이 예시는 모델 작동 확인이며 성능 검증용 데이터가 아니다.

```json
{
  "risk_score": 47.439101338386536,
  "risk_probability": 0.47439101338386536,
  "type_probabilities": {
    "institution_impersonation": 0.1574646383523941,
    "money_transfer": 0.10773290693759918,
    "personal_information": 0.09540116041898727,
    "app_installation": 0.07178381830453873,
    "secrecy": 0.09276805073022842,
    "threat_pressure": 0.09349871426820755,
    "loan_fraud": 0.10238706320524216,
    "information_probing": 0.11545180529356003
  },
  "detected_types": []
}
```

`type_scores`는 위 확률 각각에 100을 곱한 값이며 8개 모두 실제 반환됐다.

## 정량 지표와 한계

모두 **TRAIN (IN-SAMPLE), 기존 학습 1,460발화**, 기본 임계값 0.5다. 피싱 Accuracy `0.8589`, Precision `0.7574`, Recall `0.7946`, F1 `0.7756`, ROC-AUC `0.9237`, Average Precision `0.8334`; TN/FP/FN/TP = `898/114/92/356`. 유형 분류는 기본 임계값에서 8개 모두 양성 예측 0건, Micro/Macro F1 `0.0000`이다. `app_installation` 학습 양성은 6건뿐이다. 독립 validation/test가 없으며, 학습에는 마스킹 원문을 사용했고 서버 추론은 LLM 보정 문장을 사용할 수 있다. 학습 사용 승인을 사람의 발화별 검수 완료로 간주하지 않는다. 상세 수치는 `artifacts/risk_speech_ai/reports/`에 있다.

## 최종 인계 전 남은 항목

1. 모델 가중치의 외부 공유 허용 여부, 수신자 및 링크 접근 범위 승인. 현재는 별도 공유 링크를 만들거나 업로드하지 않았다.
2. 서버 담당자의 `RiskAnalyzer` 구현체, 실제 checkpoint 로더와 `app.state.risk_analyzer` 등록. 현재 지정된 `ai_loader.py`는 원격 브랜치에도 없다.
3. 서버 환경에서 수령 파일 해시 확인, tokenizer 캐시/다운로드 및 메모리 확보 후 schema·샘플 추론, 누적 위험·경고·저장·JSON 응답의 통합 인수 테스트.
4. 새 대화·원자료에 대한 독립 평가와 희소 유형 개선. 현재 수치를 서비스 성능으로 표시하지 않는다.
