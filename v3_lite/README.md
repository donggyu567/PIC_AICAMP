# KoELECTRA v3 Lite — actual internal synthetic research

**모델 학습·체크포인트 생성과 합성 VALIDATION 평가는 완료했다. 종합 개선 목표는 미달하여 v2를 대체 채택하지 않는다. 사람 검수·실환경 검증·운영 배포는 미완료다.**

실제 결과는 [완료 보고서](reports/phase3_final_20261117_v1/PHASE3_COMPLETE.md), [동일 VALIDATION 비교](reports/phase3_final_20261117_v1/VALIDATION_COMPARISON.md), [정책](reports/phase3_final_20261117_v1/TRAINING_POLICY.md)에 있다. 가중치는 Git에 없으며 [인계](handoff/research_20261117_v1/SERVER_HANDOFF.md)와 [소유자 전용 Drive 분할 전송 기록](handoff/research_20261117_v1/DRIVE_DELIVERY.md)을 확인한다. 외부 계정 공유는 재시도하지 않았다.

v2 PR#37이 미병합이므로 base는 feat/koelectra-v2-final-review인 stacked PR이다. PR#35/#37과 원본 가중치·TEST·threshold는 변경하지 않았다.

## Reuse and commands

개발용 학습/회귀는 기존 내부 연구 트리에 의존한다. `PIC_V2_RESEARCH_ROOT`를 실제 v2 연구 루트로 지정한다. portable 인계 runtime은 vendor/tokenizer를 포함하므로 저장소와 내부 데이터 없이 CPU 실행 가능하다.

```powershell
$env:PIC_V2_RESEARCH_ROOT='C:/path/to/koelectra-v2-pilot-readiness'
python -B -X utf8 -m unittest discover -s v3_lite/tests -t . -v
python -B -X utf8 -m v3_lite.src.train --manifest v3_lite/data/<private-version>/research_manifest.json --data-mode research_synthetic_v3 --run-id <new-id> --regression-receipt v3_lite/reports/<fresh-check>/regression.json
```

공개 checkout에는 미검수 합성 원문이 없어 그 자료를 요구하는2개 검사는 SKIP된다. 내부 원본에서의 실제31검사 PASS와 구분한다. 데이터 없이 실제 학습이 가능하다고 주장하지 않는다. DATA_STATISTICS/해시와 별도 비공개 원문을 맞춰야 재현할 수 있다. `reviewed` 기본경로는 기존 독립2인 검수 게이트를 유지하고, 연구 허용은 별도 `research_synthetic_v3`만 사용한다. 이전 data/README의 formal 계약은 연구 manifest를 승인 데이터로 위장하는 방법이 아니다.

데이터 생성은 plan_research_data.py로 사전 가족 배치를 기록하고 build_research_data.py로 비공개 authored literals를 직렬화·검사한다. 공개 생성 코드에서 개인 첨부파일 경로를 제거하고 실제 연구 허용 요청의 SHA를 인수로 받도록 정리했다. 이는 새 데이터 생성이나 재학습을 실행했다는 뜻이 아니다. 원문 없이 공개 checkout만으로448발화를 재생성할 수 있다고 주장하지 않는다.

추가 문서: [함수별 실제 행·호출](FUNCTION_GUIDE.md), [모델 카드](handoff/research_20261117_v1/MODEL_CARD.md), [데이터 카드](handoff/research_20261117_v1/DATA_CARD.md). 원시 데이터·승인 원본·개별 logits·캐시·.pt는 공개하지 않는다. Merge와 운영 배포는 수행하지 않았다.
