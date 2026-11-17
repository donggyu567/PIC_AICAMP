# PIC 서버 배포 준비

이 문서는 **배포 구성 예시**다. 실제 서버 생성·설치·인증서 발급·운영 검증이 완료됐다는 뜻이 아니다. 기존 서버의 분석·기기 인증·파일 저장을 그대로 사용한다.

## 목표 구성

```text
Android 앱 -- HTTPS / WSS --> Caddy -- 127.0.0.1:8000 --> FastAPI
                                                     ├─ ElevenLabs / OpenAI
                                                     ├─ 위험감지 AI 체크포인트
                                                     └─ backend/data 통화·기기 정보
```

`Caddyfile.example`은 공개 도메인을 HTTPS로 받고 HTTP와 WebSocket 요청을 같은 FastAPI로 전달한다. `pic-api.service.example`은 FastAPI를 Linux에서 상시 실행하는 systemd 설정이다. 서버별 실제 도메인과 경로를 확인해 예시를 수정한 뒤 사용한다.

## 적용 전 준비

1. AWS 인스턴스의 메모리·디스크·예상 비용과 도메인을 확인한다. CPU 기반 PyTorch·모델 로딩에 필요한 실제 사양은 Linux에서 확인해야 한다.
2. DNS를 인스턴스로 연결한다. Caddy의 공개 인증서 발급을 위해 해당 도메인과 TCP 80·443 접근이 필요하다. SSH는 관리자 IP로 제한하고 TCP 8000은 외부에 열지 않는다.
3. 서버에 `/opt/pic` 프로젝트와 호환되는 Python 가상환경 `/opt/pic/.venv`를 설치한다. 현재 `requirements-ai.txt`는 Windows 환경 기준이므로 Linux 의존성·체크포인트·토크나이저 호환성을 별도로 확인한다.
4. 서비스 계정 `pic`이 `/opt/pic` 코드를 읽고 `/opt/pic/backend/data`와 `/var/cache/pic-huggingface`에 쓸 수 있도록 준비한다. 코드는 서비스 계정에서 수정할 수 없게 관리한다.
5. `/opt/pic/.env`에 서버 전용 OpenAI·ElevenLabs 키, `PIC_CONTEXT_MODEL`, 체크포인트 설정을 둔다. `server.main`은 프로젝트 루트의 `.env`를 읽는다. 파일과 상위 디렉터리 접근은 관리자와 서비스 계정으로 제한하고 저장소에 올리지 않는다. API 키 원문은 명령줄·로그에 남기지 않는다.
6. `Caddyfile.example`의 도메인을 바꿔 Caddy 설정에 적용하고, `pic-api.service.example`을 실제 경로에 맞춰 systemd에 등록한다. 시작 전 각각 설정 검증을 수행한다.

## 최초 사양 검토 (2026-11-07)

- 현재 임시 `risk_speech_v1.pt`는 약 1.35GB다. 개발 PC에서 8000 포트의 `server.main:app` 프로세스를 확인했을 때 현재 작업 집합은 약 887MiB, 프로세스 시작 이후 최대 작업 집합은 약 2,187MiB였다. Windows에서 실행 중인 프로세스의 관측값이며 Linux 서버 전체 메모리, 최대 동시 접속, 향후 모델에 필요한 메모리는 아니다.
- 첫 시연 후보는 서울 리전 Linux 일반형 4GB RAM이다. Linux에서 시작 직후 메모리·최대 메모리와 짧은 동시 요청을 확인한 뒤 여유가 부족하면 상위 사양을 선택한다. 충분하다는 검증이나 성능 보장은 아직 없다.
- AWS 공식 가격표의 일반형 공개 IPv4 Linux 예시 기준 2GB는 월 $12, 4GB는 월 $24, 8GB는 월 $44다. 실제 리전·플랜·과금 조건과 계정 혜택은 생성 화면에서 재확인하고, 도메인·백업·추가 전송량·외부 API 등 별도 비용을 포함해 예산을 결정한다. 요금은 변동될 수 있다.
- 현재 AWS 계정과 도메인은 모두 준비되지 않았다. 인스턴스 생성·도메인 구매와 비용 발생은 아직 하지 않았다.

## 접속 주소와 프록시

- 앱은 `wss://<도메인>/api/v1/stt`를 사용한다. 분석 등 HTTP API는 같은 출처의 HTTPS를 사용한다.
- FastAPI는 `127.0.0.1:8000`에서만 실행하고 단일 worker를 사용한다. 현재 통화 잠금과 요청 제한은 프로세스 내부에 있어 여러 worker에 공유되지 않는다.
- 예시 Uvicorn은 로컬 프록시 `127.0.0.1`에서 전달한 프록시 헤더만 신뢰한다. Caddy가 외부 클라이언트의 위조된 전달 헤더를 그대로 신뢰하지 않도록 기본 설정을 유지한다. 다른 프록시·로드밸런서 또는 별도 네트워크 구성을 사용하면 신뢰 범위를 다시 정해야 한다.
- 인증 실패 제한은 클라이언트 주소를 사용한다. 배포 후 서로 다른 접속이 각각 올바른 주소로 인식되는지 확인하고, 공용 네트워크 사용자들이 동시에 차단되지 않도록 제한값을 검토한다.
- 기존 앱의 토큰은 서버 출처에 묶여 있다. 로컬 서버에서 배포 서버로 전환하기 전에 **미삭제 통화와 토큰 등록·소유권 이전 방침**을 해결해야 한다. 기존 기록이 새 서버로 자동 이동하지 않는다.

## 배포 후 확인할 내용

1. 공개 HTTPS `/health`와 인증서 확인, 외부에서 8000 포트 직접 접근이 안 되는지 확인.
2. 인증 없는 요청·다른 기기의 통화 접근 차단 확인.
3. 실제 휴대폰에서 WSS 음성 → 마스킹 → 분석 → 종료 결과 확인.
4. 동의 철회·서버 기록 삭제 및 오류 재시도 확인.
5. 서버 재시작 후 토큰·기록 유지, 요청 제한, 메모리·디스크·API 사용량 확인.

복구용 백업을 쓰면 기존 삭제 요청과 백업 보존 기간의 관계를 정해야 한다. 토큰 발급 CLI는 파일 잠금이 프로세스 간 공유되지 않으므로 **서버가 중지된 동안에만** 사용한다. `.env`, AI 체크포인트, 인증 저장소는 Git에 올리지 않는다.

## 참고 문서

- [Caddy 리버스 프록시 및 WebSocket](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Caddy HTTPS 설정 조건](https://caddyserver.com/docs/quick-starts/reverse-proxy)
- [AWS Lightsail 방화벽](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-firewall-and-port-mappings-in-amazon-lightsail.html)
- [AWS Lightsail 가격표](https://aws.amazon.com/lightsail/pricing/)
- [AWS Lightsail 사용 가능 리전](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html)
