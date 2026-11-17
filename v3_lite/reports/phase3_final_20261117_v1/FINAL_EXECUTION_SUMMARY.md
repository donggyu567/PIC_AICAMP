# Final execution summary — 2026-11-18 recovery

모델 학습·체크포인트 생성 완료. 연구용 합성 VALIDATION 평가 완료. 종합 개선 목표 미달, v2 대체 미채택. 사람 검수·실환경·운영 배포 미완료.

재학습/추가 epoch/threshold 탐색/기존 TEST 재접근 없이 기존 실제 결과를 복구했다. 1epoch·106updates·loss0.6600795072·1238.187초·201텐서 변경이다. 같은 신규 VALIDATION에서 위험F1 0.7563→0.8276, 정보탐색TP0→5, 정상대화FP6/12→3/12, 개인정보F1 0.4375→0.4211이다. 전체8유형 P/R/F1/AP는 VALIDATION_COMPARISON.md/json에 있다. 새 독립 TEST가 없어 최종 일반화 개선은 미확정이다.

내부31 PASS/0 FAIL/0 SKIP(기존27 포함), v2 core48 PASS/0 FAIL/0 SKIP는 원래 receipt와 현재 소스·모델 해시를 대조해 재사용했다. 오늘 공개 checkout에서31개 실행:29 PASS/0 FAIL/0 ERROR/2 SKIP(비공개 연구 원문 필요). 실제 명령은 RECOVERY_EVIDENCE.json에 있다. 정식 미승인 데이터 차단·기존TEST 경로 차단·별도 저장·warm start·loss/optimizer 검사를 포함한다. 독립 CPU/CLI 검증과 원격7조각 다운로드·재조립은 기존 PASS 증거와 현재 파일 SHA를 대조했다.

공개 제출물에는 코드/테스트/집계/카드/vendor/tokenizer/비밀 없는 manifest만 포함한다. .pt·분할 바이너리·미검수 TRAIN/VALIDATION 원문·승인/공유 진단 원본·개인 계정은 제외했다. 원문 부재로 공개 checkout만으로 학습을 완전히 재현할 수 없음을 명시한다. 함수196개의 실제 경로·행·signature·호출·검증은 FUNCTION_GUIDE.md와 function_index.json에 있다.

Drive7조각 업로드와 무손실 재조립 SHA 검증은 완료. 단일.pt 업로드와 소형 manifest/도구의 Drive 업로드는 완료되지 않았다. 도구/manifest는 Git으로 제공한다. 현재 소유자 전용이며 팀 공유는 미완료다. 자동 승인 검토는 외부 수신자와 비공개 모델 공유의 명시 승인이 부족하다는 이유로 공유 요청을 거절했다. 이번 복구에서 재시도·ACL변경·공개화·이동을 하지 않았다. DRIVE_DELIVERY.md에 실제7파일 링크가 있다.

v2 미병합 PR#37 head를 base로 한 feat/koelectra-v3-lite stacked Draft PR로 제출한다. PR URL/최종commit/변경 파일 수는 실제 PR 페이지와 로컬 최종 제출 receipt를 기준으로 한다. Draft 이유는 종합 개선 목표·사람검수·실서버·팀인계 미완료이며 학습 미실행 때문이 아니다. 기존PR#35/#37·모델·평가·threshold를 수정하거나 merge하지 않는다.

남은 일: 독립2인 검수/불일치 해결, 새로운 독립 TEST, 실통화/STT·HTTP/동시성/앱통합 검증, 별도 명시 승인을 받은 정확한 수신자에 대한 팀 공유, 운영 배포 승인이다. 공유/merge/운영 배포는 이번에 실행하지 않는다.
