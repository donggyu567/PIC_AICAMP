# Android v2 인수인계

최종 갱신: 2026-10-29. 앱 담당자가 다른 Codex 대화/PC에서 이어서 작업할 때의 시작점이다.
**사용자의 최신 결정: 다음 작업은 마스킹 이식보다 서버 경유 ElevenLabs STT 연결을 먼저 진행한다.**
이 문서는 진행 현황·전달 방법을 설명한다. 프로토콜의 최종 기준은 서버 담당자가 관리하는 최신 APP_SERVER_CONTRACT.md다.

## 1. 전달할 폴더

### 앱 담당자에게 반드시 전달

현재 PC의 C:/Archive/005.code/PIC_AICAMP_ANDROID에서 아래 항목을 원래 상대 경로를 유지해 전달한다.

- AGENTS.md
- PIC 프로젝트_기능명세서_2026-10-28.md
- android/ : 현재 v2 앱 소스, Gradle 설정과 Wrapper, build.ps1, 테스트, README.md, IMPLEMENTATION_PLAN.md, 이 HANDOFF.md.
- android_legacy/ : 기존 마이크 수집·마스킹 재사용 소스와 관련 테스트. 후속 이식에 필요하다.
- server/document/APP_SERVER_CONTRACT.md : 이 저장소에 동봉한 앱·서버 연결 계약. 새 담당자도 반드시 읽는다. 2026-10-29 현재 원본 서버 계약과 파일 해시가 동일하다.

android/gradle/wrapper/gradle-wrapper.jar는 빌드 도구이므로 포함한다. 앱의 현재 실행에 NER·STT 모델은 필요하지 않다.
최신 APK는 확인용으로 android/app/build/outputs/apk/debug/app-debug.apk 하나만 선택적으로 전달한다.
디자인을 다시 확인하려면 Figma 파일 접근 권한도 전달받아야 한다:
https://www.figma.com/design/4u4iy7a53GlKadKIiKAWU0/?node-id=1-396

### 서버 쪽에서 함께 전달받을 것

이 저장소의 server/document/APP_SERVER_CONTRACT.md를 먼저 읽는다. 아래 원본 서버 작업 폴더에 접근할 수 있으면 최신본과 대조하고, 다르면 서버 담당자의 최신 계약을 전달본에 반영한다. 다른 PC에서는 동봉된 계약으로 시작하고 서버 담당자에게 최신 여부·접속 주소를 확인한다. 앱 폴더 안 backend/나 다른 브랜치의 오래된 문서로 대체하지 않는다.

- C:/Archive/005.code/PIC_AICAMP/AGENTS.md
- C:/Archive/005.code/PIC_AICAMP/README.md
- C:/Archive/005.code/PIC_AICAMP/server/README.md
- C:/Archive/005.code/PIC_AICAMP/server/document/APP_SERVER_CONTRACT.md
- C:/Archive/005.code/PIC_AICAMP/server/document/CONTEXT_RISK_CONTRACT.md (후속 문맥 분석 참고)

앱만 구현하고 서버 담당자가 서버를 제공한다면 최신 계약·접속 주소·실행 버전을 공유받으면 된다.
받는 사람도 서버를 직접 실행할 경우 **서버 담당자의 최신 PIC_AICAMP 저장소 작업 내용**도 받아야 한다.
server/만 복사해서는 부족하다. server/main.py가 backend.lifespan 및 분석 라우터를 불러오고 기존 backend·models·risk_speech_ai 모듈을 사용한다.
따라서 서버용 프로젝트의 소스·requirements.txt·.env.example와 필요한 하위 모듈을 함께 전달하고, 가상환경은 받는 PC에서 다시 만든다.
현재 서버 브랜치는 feature/server-v2.0-stt-relay다. 서버 쪽 미커밋 작업도 빠지지 않도록 서버 담당자가 전달 시점을 확정해야 한다.

### 제외할 것

- 앱/Gradle 캐시: android/.gradle/, android/.gradle-work/, android/.kotlin/
- 생성 결과: 각 build/ 폴더. 최신 APK 하나는 위 설명대로 선택 전달.
- PC별 설정: .idea/, android/local.properties
- 서버 가상환경·캐시: .venv*/, __pycache__/, 임시 실행 파일
- API 키·인증 정보가 든 .env 및 비밀 파일. .env.example만 전달하고 키는 서버 환경변수로 별도 설정.
- .codex 작업트리/캐시, Android SDK, JDK, 에뮬레이터 이미지

현재 Gradle 캐시는 기존 파일의 하드링크·폴더 연결을 사용한다. 캐시를 통째로 보내지 말고 받는 PC에서 의존성을 다시 받는다.
android_legacy의 NER model.onnx와 ONNX Runtime AAR에는 실제 바이너리 대신 Git LFS 포인터가 있는 것으로 이전 단계에서 확인했다. 마스킹 단계에서는 실제 자산을 별도 준비해야 한다.

## 2. Git 전달 시 주의

현재 앱 작업 브랜치는 feature/android-v2.0이지만, 새 앱 구성과 문서에는 **미커밋·미추적 변경이 남아 있다.**
GitHub 브랜치 이름만 알려주거나 해당 브랜치를 clone하는 것으로 현재 작업 전체를 전달했다고 간주하지 않는다.
이번 인수인계 문서 정리에서도 커밋·푸시는 수행하지 않았다.

PIC_AICAMP_ANDROID/.git은 일반 .git 디렉터리가 아닌 아래 PC 경로를 가리키는 작업트리 포인터다.

C:/Archive/005.code/PIC_AICAMP/.git/worktrees/PIC_AICAMP

이 .git 파일을 다른 PC로 그대로 복사하면 독립 저장소로 사용할 수 없다.
현재 상태를 폴더로 전달할 때에는 .git 포인터를 제외하고, 받는 사람이 독립 저장소/정상 clone에 전달받은 소스를 반영하도록 한다.
Git으로만 전달하려면 담당자가 먼저 현재 앱 변경사항과 android_legacy 이동을 확인해 커밋·푸시하고 서버 쪽 최신 변경도 별도로 전달해야 한다.
인수인계를 이유로 서버 브랜치의 변경을 앱 브랜치에 일괄 덮어쓰거나 기존 파일을 자동 삭제하지 않는다.

## 3. Codex가 읽을 순서와 작업 위치

1. 앱 루트 AGENTS.md.
2. android/HANDOFF.md (이 문서).
3. android/README.md : 현재 구현·검증·빌드 방법.
4. android/IMPLEMENTATION_PLAN.md : 변경한 순서와 완료 기준.
5. 앱 루트 PIC 프로젝트_기능명세서_2026-10-28.md.
6. 이 저장소의 server/document/APP_SERVER_CONTRACT.md. 서버 쪽 루트 AGENTS.md·README.md, server/README.md와 최신 원본 계약은 접근 가능한 경우 함께 확인한다.

현재 PC에서는 명령 실행 위치를 C:/Archive/005.code/PIC_AICAMP로 하고 앱 수정 결과만 C:/Archive/005.code/PIC_AICAMP_ANDROID/android에 둔다.
Codex 대화의 자동 cwd가 과거 .codex/worktrees 경로일 수 있으므로 명령마다 workdir를 명시한다.
다른 PC에서는 두 프로젝트의 실제 위치를 정한 뒤 AGENTS.md·문서의 절대 경로를 그 위치로 조정한다.
서버 코드는 앱 작업의 결과 폴더가 아니며 서버 담당자의 작업을 덮어쓰지 않는다.
비텍스트 파일 생성은 AGENTS.md의 사용자 확인 지침을 따른다.

서버 문서의 STT·앱 작업 '보류'는 이전 결정이다. **이번 인수인계의 앱 다음 작업 순서는 사용자의 2026-10-29 요청에 따라 STT 선연결로 변경**했다.
서버 계약의 메시지 형식과 실패 처리 규칙은 계속 최신본을 따른다. 서버 담당자 작업의 우선순위를 이 문서로 임의 변경하지 않는다.

## 4. 지금까지 구현한 것

- Kotlin·Compose·Material3 새 앱, 안내/동의/권한/홈/분석/상세/최종 결과/데이터/철회 화면.
- 로딩·빈 결과·오류·종료 마무리·삭제 대기와 재시도 UI.
- DataStore 동의 상태 저장, 실제 Android 마이크 권한 요청·앱 설정 연결.
- ViewModel에서 화면 이동·회전 중 로컬 상태 유지. 프로세스 재시작은 동의만 다시 읽고 분석/결과/권한은 복원하지 않음.
- 철회 즉시 결과 삭제·늦은 모의 응답 차단, 동의 저장 실패 시 시작 차단과 재시도.
- 권한 회수 시 마지막 성공 결과를 유지하며 미완료 처리. 새 분석은 이전 점수·발화를 초기화.
- 분석 점수·발화·서버 삭제 응답은 DEBUG 예시다. 실제 녹음/전송/마스킹/서버 삭제는 미연결.
- 사용자 화면 용어는 '분석', '새 분석 시작'. 이미지 자산은 추가하지 않음. 홈 디자인은 추후 정보량을 줄이고 시작 행동 중심으로 개선할 예정.

주요 진입점:
- android/app/src/main/java/com/example/pic_ai_app/MainActivity.kt
- presentation/PicApp.kt : 화면·권한 런처·개발용 모의 타이머.
- presentation/session/SessionViewModel.kt, SessionAccess.kt : 동의·권한·로컬 상태.
- data/consent/ConsentStore.kt : 실제 DataStore 저장.
- presentation/preview/PreviewFlow.kt : 모의 분석 상태·예시 결과. 실제 통신 성공으로 취급하지 않음.
- presentation/screens/PreviewScreens.kt, presentation/home/HomeScreen.kt : 화면.

검증 기록:
- APK 2.0.2, versionCode 3, applicationId com.example.pic_ai_app.v2.
- assembleDebug·lintDebug 성공, 단위 테스트 20개 통과, Lint 오류 0개/업데이트 권고 7개.
- 실제 기기의 권한 창·물리 DataStore 저장·화면 회전은 직접 검증하지 못함.
- 로컬 AVD는 이름만 있고 시스템 이미지 실파일이 없어 실행하지 못함.
- Figma MCP 호출 한도 때문에 최근 재조회는 수행하지 못했으며 대화에서 앞서 확인한 시안을 사용함.
- 기존 APK는 교체하고 최신 APK 하나만 유지한다. build.ps1에 성공 후 출력 폴더 정리 기능이 있다.

## 5. 다음 작업: 서버 경유 ElevenLabs STT

연결할 구간은 **앱 마이크 → PIC 서버 WS /api/v1/stt → ElevenLabs → 앱 확정 결과 수신**이다.
앱이 ElevenLabs에 직접 연결하지 않는다. 키는 서버의 ELEVENLABS_API_KEY 환경변수에만 둔다.
새 서버는 중계 코드와 대체 공급자 테스트가 있으나 실제 ElevenLabs 키·음성 및 Android 연결은 미검증이다.

권장 진행 순서:

1. 서버 최신 계약과 실행 코드를 대조하고, 서버 주소·실행 버전·키 설정 여부를 확인한다. 키 값을 코드나 로그로 출력하지 않는다. .env.example은 안내용이며 서버에서 자동 로딩되지 않는다.
2. 기존 android_legacy의 audio/AndroidPcmAudioRecorder.kt에서 수집·중지 구조를 재사용한다. FloatArray 콜백을 계약의 16kHz·모노·PCM16 little-endian 바이너리로 맞춘다.
3. 앱에 실제 WS 클라이언트와 필요한 네트워크 설정을 추가한다. 동의·OS 권한 확인 → 접속 → start → ready 순서를 지킨다. ready 전에는 수집·전송하지 않는다.
4. 권장 100ms/3,200바이트 청크로 실시간 전송하고 대기열이 무한히 쌓이지 않게 한다. 녹음 파일은 만들지 않는다.
5. ready의 conversation_id 및 transcript의 utterance_id로 세션·발화를 구분한다. recognizing/finalizing은 상태만 표시한다. 모의 타이머·예시 위험도와 실제 통신 상태를 섞지 않는다.
6. 마스킹 연결 전에는 transcript.text를 메모리에서 일시 수신 후 폐기하고 수신 상태·개수만 확인한다. **원문 UI 표시·파일/로그 저장·후속 위험 분석 전송은 막는다.** 실시간 텍스트 표시는 마스킹 연결 후 진행한다.
7. 일반 종료는 수집부터 멈추고 마지막 청크 뒤 stop을 보낸다. 마지막 transcript와 stopped를 기다린다. stopped는 STT 종료이며 전체 위험 분석 완료가 아니다.
8. 권한 회수·철회·네트워크 실패 시 즉시 수집/전송 중단, 과거 세션 결과 폐기. 10분 제한·무음·짧은 음성·중복 시작·종료 중 실패를 확인한다.
9. 단위/대체 서버 확인과 실제 키·마이크 확인을 구분해 기록한다. 실제 외부 API 사용 여부와 비용 발생 범위를 검증 기록에 남긴다. 인수인계 문서 작성만으로 외부 API를 호출하지 않았다.

현재 서버의 manual 확정은 최대 5초 구간이며 완전한 문장 경계는 보장하지 않는다. 짧은 입력·무음·지연은 실제 공급자에서 확인해야 한다.
개발 PC 서버에 접속할 때 Android의 127.0.0.1은 기기 자신이다. 에뮬레이터/실기기에 맞는 서버 주소를 설정한다.
서버 프로세스를 직접 실행할 때는 PIC_AICAMP 루트와 서버 담당자 안내를 따른다. 기존 backend와 같은 저장소를 여러 프로세스에서 동시에 쓰지 않는다.

완료 기준: 허용된 실제 환경에서 음성 송신·확정 결과 수신·마지막 결과 후 정상 STT 종료·주요 실패 시 수집 중단 확인.
마스킹·위험도 계산·서버 삭제까지 연결한 것으로 보고하지 않는다.

## 6. 그 다음

1. 기존 마스킹 이식, 실제 NER 자산 준비, OTP와 추가 보호 토큰 계약 차이 해결.
2. 확정 원문을 메모리에서 마스킹하고 성공 결과만 화면·서버 위험 분석으로 연결.
3. 위험 분석 응답 점수·경고·근거 및 별도 문맥 판단 연결.
4. 전체 분석 종료·철회·삭제 API가 준비되면 통합. 현재 서버에는 이 API가 없으므로 삭제 완료를 가정하지 않음.
5. 홈 화면 재디자인과 실기기·배포 검증.

## 7. 새 담당자에게 보낼 시작 메시지

> 이 프로젝트의 Android v2 작업을 이어서 해 주세요. 먼저 앱 루트 AGENTS.md와 android/HANDOFF.md, README.md, IMPLEMENTATION_PLAN.md 및 기능명세서를 읽고 서버 쪽 최신 APP_SERVER_CONTRACT.md를 확인해 주세요. 현재 동의·권한·로컬 상태까지 구현됐고 분석은 모의 응답입니다. 다음 작업은 마스킹 이식보다 앱 마이크 → PIC 서버 → ElevenLabs STT 연결을 먼저 하는 것입니다. 마스킹 연결 전에는 인식 원문을 화면·파일·로그·후속 분석에 내보내지 말고 상태와 수신 개수로 확인해 주세요. 앱 코드는 Android 작업 폴더에만 수정하고 서버 담당자의 변경을 덮어쓰지 마세요. 이전 검증·제약과 최신 APK 하나 유지 규칙도 따라 주세요.
