# PIC Android v2

현재 위치: **3단계 동의 영속화·실제 Android 마이크 권한·로컬 세션 상태 관리 구현**.
다음은 **4단계 앱 마이크·서버 경유 ElevenLabs STT 연결**입니다. 사용자의 2026-10-29 요청으로 마스킹 이식보다 먼저 진행합니다. 마스킹 연결 전에는 인식 원문을 화면·파일·로그·후속 분석에 내보내지 않고 상태·수신 개수만 확인합니다. 홈 화면 디자인은 기능 연결과 별도로 개선할 예정입니다.

- 작업 브랜치: feature/android-v2.0
- 명령 실행 위치: C:/Archive/005.code/PIC_AICAMP
- 앱 소스·설정·빌드 결과: C:/Archive/005.code/PIC_AICAMP_ANDROID/android
- 기존 앱 보존: ../android_legacy/
- 기술: Kotlin · Jetpack Compose · Material 3 · ViewModel · DataStore
- 현재 APK: 2.0.2 / versionCode 3 / com.example.pic_ai_app.v2
- 디자인 기준: https://www.figma.com/design/4u4iy7a53GlKadKIiKAWU0/?node-id=1-396

## 인수인계

다른 담당자/Codex에게 넘길 폴더·제외할 캐시·필독 문서·작업 상태·다음 연결 절차는 [HANDOFF.md](HANDOFF.md)에 정리했습니다. 현재 새 앱 변경에는 미커밋·미추적 파일이 있으므로 GitHub 브랜치만으로 최신 작업 전체가 전달되지 않습니다.

## 현재 구현 범위

- 최초 안내 → 데이터 전송 동의 → 실제 Android 마이크 권한 요청 → 홈.
- 동의/미결정/철회 상태만 앱 전용 DataStore에 저장. 동의 기록은 백업·기기 전송에서 제외.
- 동의 저장 성공 전에 분석을 시작하지 않음. 읽기·쓰기 실패 시 분석을 막고 재시도 제공.
- 현재 OS 권한을 시작 직전과 앱 복귀 때 확인. 거부 시 안내와 앱 설정 진입 제공.
- ViewModel에서 화면 이동·회전 중 같은 로컬 분석 상태 유지. 새 프로세스에서는 동의만 다시 읽으며 권한·진행 중 분석·결과를 복원하지 않음.
- 권한 회수 시 진행 분석은 미완료로 중단하고 마지막 성공 결과 유지. 이미 입력을 멈춘 종료 처리의 마지막 결과는 반영 가능.
- 철회 즉시 분석 결과를 지우고 늦은 응답 무시. 철회 저장 중 또는 저장 실패 시에도 새 분석과 모의 삭제 완료를 차단.
- 분석 진행 ↔ 상세 → 종료 확인 → 마지막 결과 반영 중 → 최종 결과.
- 무음·연결/STT/마스킹/분석 오류·종료 미완료·삭제 대기·재시도, 상태에 맞는 로딩 표시.
- 예시 응답은 DEBUG에서만 실행. 모든 화면에 실제 녹음·전송 없음 안내 유지.

**실제인 부분은 로컬 동의 저장과 OS 마이크 권한입니다.** 마이크 권한을 받아도 실제 녹음·서버 연결·마스킹은 아직 수행하지 않습니다.
점수·발화·서버 삭제 응답은 개발용 예시이며 실제 서버 삭제를 확인한 것이 아닙니다.
서버 conversation_id와 utterance_id는 서버 연결 단계에서 최신 계약에 맞춰 연결합니다. 현재 runId는 늦은 모의 응답을 구분하는 메모리 내 번호입니다.
철회 저장이 실패했다면 재시도 성공 전까지 영속화는 완료되지 않습니다. 앱을 종료하기 전 오류를 해결해야 합니다.

기존 원문 저장 경로·STT·NER 모델 자산은 새 앱에 포함하지 않았습니다.
원문·음성·분석 결과는 이번 단계에서 파일이나 DataStore에 저장하지 않습니다.

## Appetize 또는 기기에서 확인할 흐름

1. app/build/outputs/apk/debug/app-debug.apk를 업로드·설치합니다.
2. 최초 안내 → 동의하고 계속 → 마이크 권한 요청 → Android 시스템에서 허용 → 홈.
3. 거부하면 분석이 시작되지 않는지 확인합니다. 반복 거부 시 앱 설정에서 권한을 변경하고 앱으로 돌아옵니다.
4. 새 분석 시작 → 47점/72점 예시 → 상세·데이터 안내를 열었다 돌아와도 같은 분석 유지.
5. 분석 종료 → 마지막 결과 반영 중 → 최종 결과. 정상 예시는 마지막 73점입니다.
6. 같은 설치 상태에서 앱을 종료하고 다시 열어 동의 안내를 반복하지 않는지 확인합니다. 사이트에서 새 기기나 새 설치를 만들면 앱 데이터가 초기화됩니다.
7. 데이터 안내 → 동의 철회 → 저장·모의 삭제 처리 → 앱 재실행 시 재동의가 필요한지 확인합니다.
8. 홈의 미리보기 설정에서 무음·연결/STT/마스킹/분석 실패·종료 미완료·삭제 대기와 재시도를 확인합니다.
9. 새 분석에서는 이전 점수·발화를 지웁니다. 무음이나 시작 직후 종료에는 점수를 만들지 않습니다.
10. 실제 기기에서는 OS 권한을 회수한 뒤 복귀·재실행했을 때 권한 없이 분석이 시작되지 않는지 확인합니다. OS가 권한 회수와 함께 프로세스를 종료하면 진행 결과도 사라집니다.

## 실행과 빌드

Android Studio에서는 이 android 폴더를 엽니다.
검증 환경: JDK 25.0.2, Gradle 9.5.0, AGP 9.3.1, Android SDK 37.
local.properties의 sdk.dir는 각 PC에 맞게 설정하며 Git에 포함하지 않습니다.

C:/Archive/005.code/PIC_AICAMP에서 실행합니다.

```powershell
& '..\PIC_AICAMP_ANDROID\android\build.ps1'
```

기본 작업은 assembleDebug, lintDebug, testDebugUnitTest입니다.
build.ps1은 호출한 셸 위치를 바꾸지 않고 프로젝트 대상과 쓰기 캐시를 새 앱 폴더로 지정합니다.
모든 요청 작업이 성공한 뒤 APK 출력 폴더에는 최신 APK 하나만 유지합니다.

- APK: app/build/outputs/apk/debug/app-debug.apk
- Lint: app/build/reports/lint-results-debug.html
- 단위 테스트: app/build/reports/tests/testDebugUnitTest/index.html
- 캐시: .gradle/, .gradle-work/ (Git 제외)

기존 의존성은 하드링크, Gradle 배포판은 로컬 폴더 연결로 재사용했습니다. 이 설정은 Git에 포함하지 않습니다.

## 검증 기록 — 2026-10-29

- assembleDebug, lintDebug, testDebugUnitTest 통과. 최종 화면 수정 후 assembleDebug·lintDebug 재통과.
- 단위 테스트 20개 통과: 기존 모의 흐름 9개, 동의·권한·철회·재시작·저장 실패·권한 회수 11개.
- Lint 오류 0개. 의존성/도구 업데이트 권고 7개 유지.
- APK 메타데이터 2.0.2 / versionCode 3 확인. 새 앱 작업 폴더 전체 APK 1개 확인.

실제 기기·에뮬레이터에서 시스템 권한 창, 앱 종료 후 실제 DataStore 읽기·쓰기, 화면 회전을 직접 검증하지는 못했습니다.
로컬에는 AVD 이름만 있고 실행에 필요한 시스템 이미지 실파일이 없어 새 다운로드 없이 실행할 수 없었습니다.
단위 테스트는 대체 ConsentStore와 권한 검사 함수를 사용합니다. 물리 저장소·OS 권한 창 검증을 대신하지 않습니다.
서버 통합·마스킹·녹음·실제 삭제·탐지 성능은 검증하지 않았습니다.

## 작업 지침과 다음 단계

구현 순서와 완료 기준은 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), 작업 지침은 [AGENTS.md](../AGENTS.md)를 따릅니다.
앱·서버 연동 전에는 [동봉된 앱·서버 계약](../server/document/APP_SERVER_CONTRACT.md)을 먼저 읽습니다. 현재 PC에서는 [원본 최신 계약](C:/Archive/005.code/PIC_AICAMP/server/document/APP_SERVER_CONTRACT.md)과 대조하고 서버 담당자의 최신 내용을 우선 적용합니다.
사용자 화면은 '분석', '새 분석 시작' 용어를 사용합니다.

홈 화면은 설명과 카드가 많다는 점을 개선 대상으로 남깁니다. 후속 디자인에서는 새 분석 시작을 중심으로 정보량과 배치를 정리합니다.
