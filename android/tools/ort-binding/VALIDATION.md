# Runtime validation status

Validated from application base `1d4d0349eb4281450923bc7a5940017703821c30`
and ONNX Runtime `v1.27.1` (`df2ba1cf8108aa63627cf4cdf8f807880b938616`).

- ARM64 native build: PASS.
- Official Release AAR build and publish: PASS. On this JDK 21 host, the scoped
  Java 8 compile setting in `android-jdk21.init.gradle` avoids the AGP 7.4.2
  `JdkImageTransform` failure. The native binaries remain unchanged.
- Java JNI versus sherpa runtime ELF validation: PASS. The Java JNI needs
  `libonnxruntime.so`, `OrtGetApiBase@VERS_1.27.1`, and
  `OrtSessionOptionsAppendExecutionProvider_CPU@VERS_1.27.1`; the locked sherpa
  runtime exports all three required library/symbol contracts.
- Official AAR SHA-256:
  `4dd6a6050be21fe8202c9121f49b45dcd2bf21c77bd4dc625ab40305cc90e5f1`.
- Binding-only AAR SHA-256:
  `3fde3a21dd5b422bb93afb08d92b9eb8ca20e31d2bd58879c09f94e2374f4e15`.
- Binding-only AAR generation and app file dependency: PASS.
- Application build: BLOCKED by pre-existing missing `TranscriptNer` and
  `PassThroughTranscriptNer` references in `SttViewModel.kt`. Dependency
  resolution, resource processing, duplicate-class checking, and the ORT AAR
  integration all completed before that Kotlin source failure.
- APK verification, device inference, and live STT coexistence: NOT RUN because
  no APK was produced and no Android device is connected.

The generated receipt and complete ELF command output remain under ignored
`.runtime-build/`; rerunning `build.py` regenerates them from locked inputs.
