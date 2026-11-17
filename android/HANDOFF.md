# Android 인수인계

현재 Android 앱과 서버는 한 저장소에 있다. 구현·빌드 방법은 [Android README](README.md), 통신 계약은 [앱·서버 계약](../server/document/APP_SERVER_CONTRACT.md)을 따른다.

## 새 PC에서 시작하기

1. 저장소를 clone하고 루트에서 `git lfs pull`을 실행한다. NER 모델과 ONNX Runtime AAR은 Git LFS에서 받는다.
2. JDK와 Android SDK를 설정하고 Android Studio에서 `android/`를 연다. 저장소 루트의 PowerShell에서는 `& '.\android\build.ps1'`로 실행한다.
3. 서버를 직접 구성할 때는 [서버 README](../server/README.md)를 따른다. 서버 소스는 `server/`와 함께 `backend/`, `models/`, `risk_speech_ai/`를 사용한다.
4. 이전 Android 구현을 참고할 때는 Git의 `feature/android-v3.0` 백업을 확인한다.

Gradle·빌드 캐시, `.idea/`, `android/local.properties`, Python 가상환경, API 키와 런타임 데이터는 각 PC에서 관리한다. 아래는 이전 구현 과정의 기록이다.

## 4. 지금까지 구현한 것

- Kotlin·Compose·Material3 새 앱, 안내/동의/권한/홈/분석/상세/최종 결과/데이터/철회 화면.
- 로딩·빈 결과·오류·종료 마무리·삭제 대기와 재시도 UI.
- DataStore 동의 상태 저장, 실제 Android 마이크 권한 요청·앱 설정 연결.
- ViewModel에서 화면 이동·회전 중 로컬 상태 유지. 프로세스 재시작은 동의만 다시 읽고 분석/결과/권한은 복원하지 않음.
- 철회 즉시 결과 삭제·늦은 모의 응답 차단, 동의 저장 실패 시 시작 차단과 재시도.
- 권한 회수 시 마지막 성공 결과를 유지하며 미완료 처리. 새 분석은 이전 점수·발화를 초기화.
- STT 녹음·전송 코드는 구현됐으며 실제 음성·기기 검증은 남았다. 마스킹·위험 분석·서버 삭제는 미연결.
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

## 5. STT 연결 시 참고한 작업 계획

연결할 구간은 **앱 마이크 → PIC 서버 WS /api/v1/stt → ElevenLabs → 앱 확정 결과 수신**이다.
앱이 ElevenLabs에 직접 연결하지 않는다. 키는 서버의 ELEVENLABS_API_KEY 환경변수에만 둔다.
새 서버는 중계 코드와 대체 공급자 테스트가 있으나 실제 ElevenLabs 키·음성 및 Android 연결은 미검증이다.

권장 진행 순서:

1. 서버 최신 계약과 실행 코드를 대조하고, 서버 주소·실행 버전·키 설정 여부를 확인한다. 키 값을 코드나 로그로 출력하지 않는다. .env.example은 안내용이며 서버에서 자동 로딩되지 않는다.
2. 이전 앱의 AndroidPcmAudioRecorder에서 수집·중지 구조를 재사용한다. FloatArray 콜백을 계약의 16kHz·모노·PCM16 little-endian 바이너리로 맞춘다.
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

## 7. 이전 인수인계 당시 시작 메시지

> 이 프로젝트의 Android v2 작업을 이어서 해 주세요. 먼저 앱 루트 AGENTS.md와 android/HANDOFF.md, README.md, IMPLEMENTATION_PLAN.md 및 기능명세서를 읽고 서버 쪽 최신 APP_SERVER_CONTRACT.md를 확인해 주세요. 현재 동의·권한·로컬 상태까지 구현됐고 분석은 모의 응답입니다. 다음 작업은 마스킹 이식보다 앱 마이크 → PIC 서버 → ElevenLabs STT 연결을 먼저 하는 것입니다. 마스킹 연결 전에는 인식 원문을 화면·파일·로그·후속 분석에 내보내지 말고 상태와 수신 개수로 확인해 주세요. 앱 코드는 Android 작업 폴더에만 수정하고 서버 담당자의 변경을 덮어쓰지 마세요. 이전 검증·제약과 최신 APK 하나 유지 규칙도 따라 주세요.
