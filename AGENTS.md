# Repository guidance

- Read the root [README.md](README.md) before planning or changing this project. It defines the current target pipeline and takes precedence over older project proposals.
- Follow this target order: app microphone → server relay to ElevenLabs real-time STT → transcript returned to app → masking on device → masked text sent to server → single OpenAI call for correction and contextual risk judgment → existing AI risk calculation → result returned to the app.
- Distinguish verified server code and sample API calls from unverified judgment quality, ElevenLabs audio integration, Android integration, and always-on AWS Lightsail 2 deployment. Do not describe pre-masking audio as remaining on device.
- Use `server/README.md` for the new server's implementation order, current progress, and next task. Use `backend/document/README.md` for existing backend behavior and API details; do not treat existing features as already connected to the new server.
- Before creating a new non-text file, such as an image or spreadsheet, ask the user and create it only after they agree.

## 구현·검증 범위

- 요청한 기능과 직접 영향을 받는 경로에 집중한다. 별도 요청이나 구체적인 결함 근거 없이 프로젝트 전체 감사, 깊은 예외 탐색, 추가 리팩터링으로 범위를 넓히지 않는다.
- 검증은 변경한 기능의 정상 흐름과 실제 발생 가능한 주요 실패 상황을 중심으로 한다. 기존 관련 테스트를 우선 사용하고, 구현을 그대로 반복하는 테스트나 영향이 작은 변경을 위한 불필요한 테스트는 추가하지 않는다.
- 관련 검증이 통과하면 작업을 마무리한다. 이후 코드 변경, 테스트 실패, 해결되지 않은 구체적 문제가 있을 때만 필요한 검증을 다시 실행한다. 같은 파일·로직을 새 근거 없이 반복 검토하지 않는다.
- 입력·외부 응답·저장 데이터의 검증 책임을 명확한 경계에 둔다. 이미 검증한 값을 내부 함수마다 다시 검사하거나, 같은 조건을 여러 계층에서 중복 구현하지 않는다. 별도 진입점에 필요한 검증은 유지한다.
- 현재 요구사항을 충족하는 가장 단순한 구현을 선택한다. 가상의 미래 요구사항이나 드문 상황만을 위한 추상화, 호환 계층, 복구 체계, 방어 코드를 추가하지 않는다. 공통화는 실제 중복이 있고 코드가 더 단순해질 때 적용한다.
- 개인정보 마스킹 실패 시 전송 차단, 데이터 유실·중복 저장 방지, 외부 서비스 실패 처리 등 현재 기능의 핵심 보호는 유지한다. 위험감지·마스킹 모델의 판단 기준은 별도 요구사항에 따라 변경한다.
- 요청 범위 밖의 개선점은 짧게 보고하고 임의로 구현하지 않는다. 기존 코드·테스트의 대규모 삭제는 별도 정리 작업으로 다룬다.
- 완료 보고는 변경 내용, 수행한 검증, 남은 제한 사항을 간단히 전달한다. 검증하지 않은 부분을 완료했다고 표현하지 않는다.

## 기존 코드 재사용

- 새 서버의 각 단계를 구현하기 전에 해당 기능의 기존 코드와 `backend/document/README.md`의 계약을 확인한다. 현재 파이프라인에 맞는 기존 구현을 우선 재사용하며, 새 서버라는 이유만으로 같은 기능을 다시 작성하지 않는다.
- 그대로 쓸 수 있는 모듈은 직접 호출하고, 계약 차이는 필요한 입출력 변환으로 해결한다. 이식이 필요하면 해당 단계의 범위에 한정한다. 중복 구현이나 불필요한 호환 계층을 추가하지 않는다.
- 기존 `backend`는 전환 중 보존한다. 재사용을 이유로 기존 코드·테스트를 임의로 삭제하거나 프로젝트 전체를 리팩터링하지 않는다.
- 작업 설명에서 재사용할 파일·함수와 새로 만들 부분을 구분한다. 연결 후 `server/README.md`에 실제 재사용 경로와 검증 범위를 기록하며, 재사용 후보와 연결 완료 상태를 구분한다.

## 새 서버 진행 기록

- 새 서버 작업을 계획하거나 진행 상황을 보고할 때는 `server/README.md`의 현재 위치와 구현 순서를 먼저 확인한다.
- 해당 단계의 기능 요구사항은 `PIC 프로젝트_기능명세서_2026-10-28.md`와 `server/README.md`의 기능 명세 적용 방침을 함께 확인한다. 기존 backend 동작을 새 정책으로 오인하지 않으며, 일반 종료의 마지막 결과 반영과 동의 철회의 중단·삭제를 구분한다.
- 작업 시작 시 이번 작업이 목표 파이프라인의 어느 구간인지와 현재 완료 단계를 짧게 알린다. 전체 계획을 매번 반복하지 않는다.
- 단계 작업을 마치면 `server/README.md`에 실제 구현·연결·검증 범위와 다음 작업을 갱신한다. 계획, 기존 코드의 존재, 새 서버 연결 완료를 구분한다.
