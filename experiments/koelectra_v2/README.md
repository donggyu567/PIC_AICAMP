# KoELECTRA v2 내부 연구 실행기와 공개 검토 범위

1~5차의 실제 데이터 확장·6개 학습 궤적·18개 epoch checkpoint·고정 계획 1회 TEST 평가 구현이다. 공개 코드는 연구용 인계이며 운영 배포 승인이나 인간 라벨 검수를 뜻하지 않는다. 예전 preflight-only 계획과 실제 4차 연구 실행을 구분한다.

- `expanded_data.py`/`expanded_cli.py`: 정식 승인 Partition 및 실행기. 기존 권한·검수 게이트를 유지한다.
- `stage3_data.py`/`stage3_research.py`: 구조·중복·마스킹 검사와 별도의 provisional/internal_experiment 어댑터. TRAIN/VALIDATION만 읽는다.
- `expanded_training.py`/`expanded_checkpoint.py`/`expanded_selection.py`/`expanded_evaluation.py`: 가중 손실·checkpoint·VALIDATION 선택·지표와 정식 A/B/C 실행 구성.
- `stage4_exploratory.py`: 실제 실행한 6개 A_epoch/B_ratio 궤적. 별도 연구 metadata와 false 승인 상태를 유지한다.
- `stage3_seal.py`/`stage5_custody.py`: DPAPI/ACL 보관 및 실제 보관자 승인·동결 바인딩·고정 one-time claim. 보호된 영수증·승인·TEST는 이 저장소에 없으며 기존 TEST를 다시 열어서는 안 된다.
- `stage5_runtime.py`: 모델·tokenizer·manifest 검증과 서버용 현재 발화 추론. 최종 복사본은 `artifacts/v2_research_handoff/stage5_final_20261110_v1/stage5_runtime.py`다.
- `check_public_release.py`: 공개 자료만으로 실행할 AI 회귀 검사. 내부 자료 의존 검사는 명시적으로 skip한다.
- `protocol_20261109_v1.json`: 과거 사전 등록 정식 설계 원본. 그 안의 design-only/미확보 상태를 실제 연구 실행 완료로 바꾸지 않았다. 실제 실행 상태는 공개 보고서의 training comparison과 final evaluation에 있다.

루트 `risk_speech_ai/` 디렉터리를 새 운영 모듈로 만들지 않았다. 실제 재사용 코드는 `artifacts/v1_reference/pr35_9bab7e383928/risk_speech_ai/`, portable 인계 코드는 `artifacts/v2_research_handoff/stage5_final_20261110_v1/vendor/risk_speech_ai/`다. PR35는 별도 열린 PR이며 수정/병합하지 않았다.

## 실행·자료 제한

```powershell
python -B -X utf8 experiments/koelectra_v2/check_public_release.py --output reports/public_checks_new.json
```

Python3.11, torch2.6.0+cpu, transformers4.57.6 등 실제 의존성은 최종 패키지 requirements-tested.txt에 있다. 공개 단위 검사도 tokenizer/config의 고정 revision 캐시가 필요하다. 실험의 기본 오프라인 캐시 경로는 `Path(repository).parents[1] / '.venv-ai/hf-cache/hub'`이므로 일반 checkout에서는 그 위치에 공개 모델 tokenizer/config를 준비하거나 실행기 cache 인수를 명시한다. 원격 CI에서 이 환경을 실행한 것으로 표시하지 않는다. 실제 모델 weights·연구 원문·승인 증빙은 공개하지 않아 전체 학습과 최종 TEST를 public checkout만으로 재실행할 수 없다. `check_public_release.py`는 실제 연구 모델을 재학습하거나 TEST를 읽지 않는다.

리뷰 진입점: [reports/v2_public_release_20261110/README.md](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/reports/v2_public_release_20261110/README.md), [reports/v2_public_release_20261110/FUNCTION_GUIDE.md](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/reports/v2_public_release_20261110/FUNCTION_GUIDE.md).
