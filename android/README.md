# PIC Android v2

**2026-11-09 현재:** ElevenLabs STT 중계, 기기 내 마스킹, 서버 위험 분석·결과 표시와 통화 종료를 연결했다. AWS 서버에 수동 등록한 기기로 위험 점수 표시를 확인했으며, 자동 기기 등록 코드는 연결했지만 신규 기기 실연결 검증은 아직 필요하다. 아래의 이전 단계 기록은 작성 당시 상태다.

팀원은 Git LFS를 설치한 뒤 `git lfs pull`로 NER 모델과 ONNX Runtime AAR을 받아야 한다. Android Studio에서 `android/` 폴더를 연다. NER·위험 탐지 성능은 별도 검증이 필요하다.

更新: 2026-11-05

4段階のマイク・サーバー経由STT接続を実装。代替サーバーとマイクによる単位テスト、ビルド・Lintが通過。実機と実サーバーを組み合わせた音声認識は未検証。

- 作業ブランチ: feature/android-v2.0
- 命令実行: C:/Archive/005.code/PIC_AICAMP
- アプリ: C:/Archive/005.code/PIC_AICAMP_ANDROID/android
- 旧アプリ: ../android_legacy
- APK: 2.0.3 / versionCode 4 / com.example.pic_ai_app.v2

## 実装状況

- 初回案内、DataStoreによる同意保存、OSマイク権限要求・設定画面への移動。
- 既存 AudioRecord の収集・停止構造を再利用し、16kHz モノ PCM16 little-endianのバイナリに変換。
- サーバーへのWebSocket接続とstart、ready受信後の録音・音声送信、発話数と進行状態の表示。
- 終了操作時のマイク停止・stop送信・最後のtranscriptとstopped待ち。接続失敗、権限拒否、送信エラー、待ち時間超過、10分制限を処理。
- 同意撤回・権限回収時は録音とWebSocketを中断。旧セッションのコールバックは破棄。
- STT確定発話を既存NER・Regex・Ruleでマスキングし、成功時の文だけ画面に表示。元文は表示・保存・分析送信しない。失敗時は処理を停止する。
- リスク分析と結果表示を接続。実際のサーバー記録削除・最終分析確定・通知、分析失敗の再試行は未接続。
- ホーム画面のデザイン改善は後続作業。

## 接続方法

DEBUG版ホームの「STTサーバー WebSocket アドレス」に接続先を入力する。既定値 ws://10.0.2.2:8000/api/v1/stt はAndroid標準エミュレーター上の開発PCを指す。
実機では到達可能な開発PCのアドレスまたは公開サーバーのwssアドレスが必要。Appetize等のクラウド端末からはローカルPCの10.0.2.2に接続できない。
ws接続はデバッグ構成のみ許可。公開時はWSS・接続先設定を整える。アドレスは現在のアプリ実行中のみ保持する。
サーバーは最新 server/document/APP_SERVER_CONTRACT.md に合わせて起動し、ElevenLabs APIキーはサーバー側で設定する。

## 検証

2026-11-05、assembleDebug・lintDebug・testDebugUnitTest成功。22件の単位テストが通過。
新規2件は代替WebSocketサーバーとマイクを使用し、start→ready→音声→stop→最後の発話→stoppedの順序と、ready時の権限拒否を確認。
テストは実際のAndroidマイク、実サーバー、ElevenLabsを使用していない。接続端末とローカルサーバーがなかったため実音声・実機の動作は未確認。

## 実行

Android Studioでandroidフォルダを開く。JDK・Android SDKは実行PCに設定する。
C:/Archive/005.code/PIC_AICAMPからのビルド:

```powershell
& '..\PIC_AICAMP_ANDROID\android\build.ps1'
```

成功時にAPK出力フォルダには最新APKを1つ残す。

- APK: app/build/outputs/apk/debug/app-debug.apk
- テスト: app/build/reports/tests/testDebugUnitTest/index.html
- Lint: app/build/reports/lint-results-debug.html
- 次の作業と検証基準: IMPLEMENTATION_PLAN.md
- 引き継ぎ: HANDOFF.md
- アプリとサーバーの契約: ../server/document/APP_SERVER_CONTRACT.md。作業前にサーバー担当の最新原本と照合する。

## 마스킹 연결 검증 (2026-11-06)

- `android_legacy`의 `TranscriptMasker`, NER·Regex·Rule·Resolver·Renderer를 이식했다. Git LFS에서 실제 NER 모델과 arm64 ONNX Runtime을 받아 새 앱에 준비했다.
- STT 수신·마스킹은 별도 작업으로 처리하고 발화 순서를 유지한다. 종료 후에도 마지막 마스킹이 끝날 때까지 대기한다. 동의 철회·실패 시 중단하고 늦은 결과를 버린다.
- `assembleDebug`와 `testDebugUnitTest` 성공, 총 23개. 대체 마스커 테스트로 성공 시 마스킹 문장 표시, 원문 미표시, 실패 시 중단, 종료 대기를 확인했다. 모델의 실제 추론·개인정보 탐지 품질은 실기기에서 확인하지 않았다.
- 실제 서버 연결 시 발화 수가 증가한 것은 사용자 확인 사항이다. 실제 인식 문장의 내용과 정확도, 실기기 모델 추론·지연은 아직 확인하지 않았다.
- 현 단계는 화면 표시까지다. 위험 분석 전송은 아직 없다. 기존 마스킹 토큰 중 서버 미지원 유형 및 OTP 계약 차이는 서버 전송을 연결하기 전에 해결해야 한다.

## 실기기 ONNX 로딩 오류 수정 (2026-11-06)

- 실제 확정 발화 직후 `libonnxruntime.so` 누락으로 `UnsatisfiedLinkError`가 발생한 것을 기기 crash 로그로 확인했다. 기존 Java binding AAR은 JNI만 포함하며 ONNX core가 별도로 필요하다.
- 기존 sherpa 런타임의 arm64 ONNX core를 잠금 파일의 SHA-256과 일치하는지 확인하고 `app/src/main/jniLibs/arm64-v8a`에 포함했다. ABI는 arm64-v8a로 제한한다. 마스킹 중 LinkageError는 원문 표시 없이 실패 상태로 처리한다.
- `assembleDebug`, `testDebugUnitTest` 성공. APK에서 ONNX core·JNI·NER 모델이 함께 포함된 것을 확인했고 연결된 실기기에 설치했다. 실제 발화에 대한 기기 추론·개인정보 탐지 품질은 재확인 대기다.

## 위험 분석 및 OTP 연결 (2026-11-06)

- `RiskAnalysisClient.analyze()`가 마스킹 결과만 서버 분석 API로 전송한다. `SttSession`은 요청을 발화 순서대로 실행하고 정상 응답의 누적 점수·경고·문맥 설명을 화면에 표시한다.
- 마스킹 또는 분석 실패, 응답 유실 시 세션의 후속 분석을 중단한다. 실패를 0점으로 표시하거나 요청을 자동 재전송하지 않는다. AI 재시도·결과 조회에 의한 복구와 서버 전체 통화 종료 API 호출은 아직 없다.
- 사용자 승인으로 OTP 문맥이 있는 발화와 이어지는 최대 두 발화에서 세 자리 이상 숫자·한글 숫자열을 `[OTP]`로 마스킹한다. 모든 표현과 STT 오인식을 탐지한다는 보장은 없다.
- 새 앱의 카드·생년월일·이메일·비밀번호·불명확 토큰은 서버에서 허용하도록 계약을 확장했다. Android 단위 테스트 28개 통과 및 debug 빌드 성공. STT·HTTP·NER 대체 객체 기준이며 실기기 전체 연결은 미검증이다.
- 변경된 서버 코드를 읽도록 서버 재시작 후 새 APK를 실기기에 설치해 테스트한다. 동의 철회 시 서버 기록 삭제와 진행 중 요청의 서버 측 취소는 아직 연결되지 않았다.


## 최종 결과 화면 표시 (2026-11-06)

서버 종료 응답을 확인한 뒤 같은 분석 화면 상단에 `최종 분석 결과` 카드와 누적 점수·안내를 표시한다. 별도 화면 전환은 아니다. 사용자가 발화 목록 아래에 있던 결과를 찾기 어렵다고 알려줘 위치를 변경했다. debug 빌드와 실기기 설치는 성공, 수정 후 실제 종료 표시 확인은 대기 중이다.
