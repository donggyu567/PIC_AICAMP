# Repository guidance

- Read the root [README.md](README.md) before planning or changing this project. It defines the current target pipeline and takes precedence over older project proposals.
- Follow this target order: app microphone → server relay to ElevenLabs real-time STT → transcript returned to app → masking on device → masked text sent to server → OpenAI LLM correction → existing AI risk calculation → separate OpenAI LLM contextual risk judgment → result returned to the app.
- Treat ElevenLabs integration, contextual LLM risk judgment, and always-on AWS Lightsail 2 deployment as planned work until the code and deployment are verified. Do not describe pre-masking audio as remaining on device.
- Use `backend/document/README.md` for current server behavior and API details. Keep current implementation distinct from the target architecture.
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
