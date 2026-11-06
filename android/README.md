# PIC Android v2

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
- マスキングはまだ接続されていないため、受信原文は保持・表示・記録・分析送信せず発話数のみ表示。
- リスク分析・実際のサーバー記録削除・最終分析確定・通知は未接続。STT終了画面と処理状態のみ実データに接続した。
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
