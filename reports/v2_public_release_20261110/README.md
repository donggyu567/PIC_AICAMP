# KoELECTRA v2 공개 검토·인계 요약

실제 완료: TRAIN80/656, VALIDATION32/256, 별도 TEST40/320; A_epoch/B_ratio 각3seed×3epoch=6궤적·18checkpoint·1,476업데이트; 승인 후 TEST 1회; v1 동일 입력 비교; 연구용 portable 모델 로딩 검증. 최종 고정 epoch3·9threshold0.5·기본 seed42를 유지했다.

미완료: `.pt` Drive 업로드(공식 연결 512MiB 제한, 브라우저 URL 검증 실패), 실제 서버 전송·통합·운영 배포 승인·인간 라벨 검수. C_approved와 B_step_matched는 필수 승인 증강 자료가 없어 실행하지 않았다. 공개 PR은 Draft다.

권장 리뷰 순서:
1. [reports/v2_public_release_20261110/FINAL_REPORT.md](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/reports/v2_public_release_20261110/FINAL_REPORT.md) — 실제 TEST 지표·불확실성·취약점.
2. [reports/v2_public_release_20261110/DATA_AND_TRAINING.md](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/reports/v2_public_release_20261110/DATA_AND_TRAINING.md) — 분포·loss·epoch 결과.
3. [reports/v2_public_release_20261110/FUNCTION_GUIDE.md](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/reports/v2_public_release_20261110/FUNCTION_GUIDE.md) — 실제 함수별 줄·입력·반환·검증·연결.
4. [artifacts/v2_research_handoff/stage5_final_20261110_v1/SERVER_HANDOFF.md](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v2_research_handoff/stage5_final_20261110_v1/SERVER_HANDOFF.md) — 실행 계약/오류 처리/모델 사용.
5. [artifacts/v2_research_handoff/stage5_final_20261110_v1/DRIVE_DELIVERY.md](https://github.com/donggyu567/PIC_AICAMP/blob/feat/koelectra-v2-final-review/artifacts/v2_research_handoff/stage5_final_20261110_v1/DRIVE_DELIVERY.md) — 정확한 checkpoint·해시·업로드 차단 상태.

공개 수치는 로컬 원본에서 파생한 집계 복사본이다. `*.public.json`은 출처 hash와 제거 범위를 기록하며 원본 audit 파일과 byte-identical이라고 주장하지 않는다. 사람 SID/계정·실제 release/승인 파일·봉인 영수증/암호문·평문·키·개별 TEST 정답/logits·내부 TRAIN/VALIDATION을 제외했다. 원래 v2 브랜치의 과거 데이터/감사 변경도 이 main 기반 제출에 넣지 않았다. 원본은 로컬에서 그대로 보존한다.

권리 미확인 기존 v1 입력68대화·1,460발화는 새 연구 학습에 포함하지 않았다. 보조 LLM VALIDATION24대화·192발화도 별도 보존했다. 생성 모델 이력은 관측 가능한 Codex/GPT-6 family이며 요청한 GPT-6.1 Sol을 확인되지 않은 실제 backend ID로 위장하지 않았다. 새 라벨은 모두 잠정이다.

TRAIN/VALIDATION의 대화·가족 ID 중첩과 정규화 중복 후보는 0개였지만, 원래 TRAIN 내부 중복1개 및 v1 유사 짧은 응답1개는 기존24대화 보존을 위해 유지했다. VALIDATION 내부 유사 후보1개도 보고했다. 문자열 검사는 의미적 독립성·라벨 정답성을 인증하지 않는다. TEST 유형별 지원은 양성12발화·등록 가족4개뿐이고 정상 대화는8개다.

연구 B_ratio F1평균0.9231±0.0363은 v1단일0.4756보다 높았다. 하지만 information_probing은 세 seed 모두 TP0/FN12, 개인정보는 seed42 FP74 및 seed43/44 FN10/9, 기본서버 seed42의 정상 대화 오탐은3/8이다. 현재 모델의 실운영 적합성은 입증되지 않았다. TEST를 v2.1 모델/epoch/threshold 선택에 재사용하지 않는다.

공개 checkout 검사와 원래 작업 트리 240개 검사는 범위가 다르다. 최종 실제 실행 결과는 `public_regression.json`과 `original_regression.json`에서 확인한다. 저장소 전체 Android/백엔드 회귀 검사나 원격 CI 전체 통과로 확대 해석하지 않는다.
