# 체크포인트 인계 상태

상태: **UPLOAD_BLOCKED — 실제 .pt 업로드 미완료**.

가중치 없는 지원 ZIP만 별도로 업로드했다: https://drive.google.com/file/d/1bhgPOuqkHhWZTxPMDsEoEM3n7nJbmonm/view?usp=drivesdk
크기 436,469bytes, SHA-256 `1a063cda2d92b84d566bef59b0d01a62db733f77839b7ff9be20659b8bf23c72`. 공식 연결로 재다운로드해 원본과 일치함을 확인했다. 이 ZIP은 가중치 없는 30개 지원 파일의 업로드 당시 snapshot이며, 실제 모델 인계가 완료됐다는 뜻이 아니다.

공식 Drive 연결은 536,870,912바이트(512MiB) 제한으로 1,348,303,914바이트 원본을 거부했다. Windows 브라우저 대체 경로도 현재 URL의 신뢰성 검증 실패로 자동화가 중단됐다. 업로드 성공이나 원격 해시 일치를 주장하지 않는다.

수동 업로드 대상 폴더: https://drive.google.com/drive/folders/1hdZZMXFzYdlhZxeA5fI1m6GRe_JgCfMH

원본 경로(연구 작업 트리 기준): `artifacts/v2_research_handoff/stage5_final_20261110_v1/models/B_ratio/seed_42.pt`.
권장 업로드명: `KoELECTRA_v2_B_ratio_seed42_epoch3_20261110.pt`.
SHA-256: `0d14fadcc9dbd1a3ea3872074970d47f79148f76766d77188eb808b94ed9d2ee`.
크기: **1,348,303,914 bytes**. Seed42, epoch3, 연구용 B_ratio.

새 폴더와 기존 기술 문서 폴더 모두 기존 공유 정책상 링크 보유자 편집(anyone/writer, 검색 비공개) 권한이 관측됐다. 권한을 추가하거나 확대하지 않았다. 팀 구성원만으로 제한된 폴더라고 주장하지 않는다. 업로드 전에 이 기존 범위를 인지해야 한다.

Seed43·44는 원본 로컬에 보존했다. 추가 업로드는 하지 않았다. 각각의 크기·해시는 CHECKPOINTS.json에 있다. 로컬 최종 패키지의 tokenizer/vendor/runtime/manifest/카드를 함께 전달해야 하며, 이 Git 제출에는 가중치가 없다.

업로드 후 파일 ID·크기·접근 권한을 읽어 확인하고 가능하면 원격 SHA-256 또는 다운로드 해시를 비교해야 한다. 이후 PR의 이 상태를 실제 링크와 검증 결과로 갱신한다. 실제 서버 전송·통합, 인간 라벨 검수, 운영 배포 승인은 미완료다.
