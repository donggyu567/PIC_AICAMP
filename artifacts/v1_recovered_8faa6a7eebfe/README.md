# 과거 v1 학습 입력의 해시 검증 복구본

이 폴더는 새 합성 데이터를 담지 않습니다. Git 커밋 `8faa6a7eebfe95c7ac7fe6c6077a49ebf31f958f`의 실제 원자료 blob과 보존된 PR35 준비 코드를 이용해 과거 입력의 바이트를 복구했습니다. `prepared/labels.jsonl`과 `prepared/tuned.jsonl`은 PR35 재현성 기록의 SHA-256과 각각 정확히 일치합니다.

`source_snapshot/`은 당시 원자료의 별도 사본이며 기존 dataset 경로를 덮어쓰지 않았습니다. 이 파일들이 현재 정본이라는 뜻은 아닙니다. 복구한 입력의 과거 `approved_for_training` 필드는 역사적 파일 내용으로, 새로운 사람 승인이나 v2 학습 허가를 뜻하지 않습니다.

학습된 v1 가중치는 이 폴더에 없습니다. 실제 체크포인트는 NOT_FOUND이고 CPU 모델 로딩은 파일 미확보로 BLOCKED입니다. 자세한 경로·크기·해시·복구 방식·검색 범위는 [이번 감사 보고서](../../reports/v2_pipeline_audit/README.md)를 확인하세요.
