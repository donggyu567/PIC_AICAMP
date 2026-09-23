# ORT 1.27.1 Java binding for the existing sherpa runtime

This workflow keeps the original `sherpa-onnx-1.13.6.aar` as the only
`libonnxruntime.so` supplier. It does not use a Maven ORT dependency or
`pickFirst`. The app is not modified until the generated binding passes ELF
validation. See `VALIDATION.md` for the actual execution status, not just the
intended workflow.

## Fixed inputs

- Application base: `1d4d0349eb4281450923bc7a5940017703821c30`.
- Upstream: <https://github.com/microsoft/onnxruntime>, tag `v1.27.1`.
- Immutable source: `df2ba1cf8108aa63627cf4cdf8f807880b938616`.
- ABI `arm64-v8a`, Android API/minSdk 24, CPU provider, full FP32 operators.
- `source-lock.json` records source, NDK/CMake versions and sherpa/model hashes.
- `arm64-cpu.json` is passed to the **unmodified official**
  `tools/ci_build/github/android/build_aar_package.py`.

The official script builds both ORT core and JNI, then invokes its Android
Gradle AAR build/publish. The newly built core is an intermediate only: it is
never copied into the app. We retain Java classes and JNI from the same source
build and validate JNI against the *existing sherpa* core before packaging.

## Build

Use Python 3.11, Git, JDK 17/21 and an Android SDK with these installed packages:

```text
ndk;27.2.12479018
cmake;3.31.6
platforms;android-34
build-tools;34.0.0
```

The application itself additionally requires its existing SDK 37 and Gradle
configuration. Do not downgrade them as part of this task. The upstream Windows
AAR builder uses symlinks. If native outputs completed before a Windows symlink
privilege failure, rerun with `--package-existing` to reuse those outputs and
perform the official Gradle AAR build/publish. JDK 21 also needs the checked-in
init script because AGP 7.4.2 emits an Android JMOD target that its `jlink`
rejects; JDK 17 keeps the upstream Java 17 compile settings. Host C++ build tools
and network access may be required. These Python scripts install no dependency.

From the repository root, with `JAVA_HOME` set:

```powershell
python android/tools/ort-binding/build.py build --android-sdk "$env:ANDROID_HOME"
```

Windows resume command after the native build has completed:

```powershell
python android/tools/ort-binding/build.py build --package-existing --android-sdk "$env:ANDROID_HOME"
```

Source and generated outputs stay under ignored `.runtime-build/`. An existing
checkout must match both the tag and immutable commit and have no tracked
modifications. The wrapper records the exact command, tool versions,
submodule commits, settings hash and full AAR hash after upstream success.

Outputs, only on success:

```text
.runtime-build/official-aar-receipt.json
.runtime-build/artifacts/onnxruntime-java-binding-1.27.1-arm64.aar
.runtime-build/artifacts/onnxruntime-java-binding-1.27.1-arm64.aar.sha256
.runtime-build/artifacts/onnxruntime-java-binding-1.27.1-arm64.elf-evidence.json
.runtime-build/artifacts/onnxruntime-java-binding-1.27.1-arm64.verification.json
```

The binding ZIP has stable ordering, timestamps and permissions, and stores
entries without compression to avoid zlib-version-dependent output. The same
official input AAR gives byte-identical binding output. This does not claim
bit-for-bit reproducibility of an upstream compiler build across different
hosts; the full input AAR and toolchain are recorded for that reason.

## Postprocessing and fail-closed checks

`binding.py package` can also be invoked separately with `--full-aar`,
`--receipt`, `--sherpa`, `--readelf` and `--output`.

It preserves `classes.jar`, Android manifest, metadata and consumer rules.
Only `jni/arm64-v8a/libonnxruntime4j_jni.so` survives the native allowlist.
Every other ABI and every `libonnxruntime.so` is omitted. Original archives
are never edited in place. Duplicate archive paths are rejected.

The NDK `llvm-readelf` commands recorded in the evidence are:

```text
llvm-readelf --wide --dynamic <library>
llvm-readelf --wide --dyn-syms <library>
llvm-readelf --wide --version-info <library>
llvm-readelf --wide --program-headers <library>
```

Both sherpa JNI and Java JNI must dynamically need `libonnxruntime.so` and
import `OrtGetApiBase@VERS_1.27.1`. The locked sherpa runtime must export it.
All imported ORT symbols (including provider entry points) must be satisfied,
with matching versions. ELF64 little-endian/AArch64 is required. A JNI that
defines its own `OrtGetApiBase` is rejected. Failure emits evidence but does
not produce a new binding AAR or modify Gradle. Do not reuse an older output
after a failed build; use the successful invocation's receipt and checksum.

Audit existing binaries independently:

```powershell
python android/tools/ort-binding/binding.py audit-elf --sherpa android/app/libs/sherpa-onnx-1.13.6.aar --readelf "$env:ANDROID_NDK_HOME/toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-readelf.exe" --report .runtime-build/sherpa-elf.json
```

Supply `--java-so <file>` to validate an actual new JNI too. An audit without
that argument proves only the existing sherpa side.

## App integration, strictly after ELF success

Copy the verified artifact into `android/app/libs/`, then add only this beside
the existing sherpa file dependency:

```kotlin
implementation(files("libs/onnxruntime-java-binding-1.27.1-arm64.aar"))
```

Retain the verification report and SHA-256 alongside the delivery. Existing
LFS rules already cover `android/app/libs/*.aar`. Do not add Maven aliases,
packaging exclusions or `pickFirst`.

Fetch the fixed model (hash checked before writing):

```powershell
python android/tools/ort-binding/build.py model --output android/app/src/main/assets/models/koelectra-ko-pii-ner/model.onnx
```

Model source: <https://huggingface.co/atonlee/koelectra-ko-pii-ner/tree/1e75c01e707232401883cf364151bbe2e560c708>.
Model weights are Apache-2.0 according to that repository. This is the FP32
`onnx/model.onnx`, not a quantized variant.

Copy the staged `smoke/OrtSherpaRuntimeSmokeTest.kt` into
`android/app/src/androidTest/java/com/example/pic_ai_app/masking/runtime/`
only when the binding dependency is available. Keeping this source staged
avoids adding unresolved Java API imports to the current application.

```powershell
cd android
./gradlew.bat :app:assembleDebug :app:assembleDebugAndroidTest --console=plain
```

From the repository root inspect the *actual* APK:

```powershell
python android/tools/ort-binding/binding.py verify-apk --apk android/app/build/outputs/apk/debug/app-debug.apk --sherpa android/app/libs/sherpa-onnx-1.13.6.aar --binding android/app/libs/onnxruntime-java-binding-1.27.1-arm64.aar --readelf "$env:ANDROID_NDK_HOME/toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-readelf.exe" --report .runtime-build/apk-verification.json
```

The verifier checks duplicate ZIP entries, ABI, exact native names and AAR
byte provenance. A changed/stripped binary fails for investigation rather
than silently accepting a different supplier. The intended APK contains
the original four sherpa AAR libraries plus Java JNI from the binding AAR.

## Runtime smoke and limits

On a connected ARM64 device, run the class with:

```powershell
./gradlew.bat :app:connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.example.pic_ai_app.masking.runtime.OrtSherpaRuntimeSmokeTest
```

The tests assert runtime 1.27.1, model SHA, the two INT64 inputs, FP32 logits,
dummy `[CLS, UNK, UNK, SEP]` inference with shape `[1, 4, 59]` and finite
values. Both load orders are covered with a live sherpa recognizer. Tensor,
result, session and session-option resources are closed. The environment
is the process-wide ORT singleton. STT receives silence; this checks basic
initialization/decoding and **does not measure speech recognition accuracy**.

No tokenizer, span mapping, BIO decoding, detector, renderer or pipeline
integration is included. Missing `TranscriptNer`/`PassThroughTranscriptNer`
in the base branch is out of scope. A successful ELF check alone does not
authorize claiming Android inference or STT success.

If genuine runtime/JNI incompatibility remains, evaluate rebuilding sherpa
against the exact upstream core (fallback A), or a minimal C API JNI bridge
(fallback B). Neither fallback is implemented here.

Script checks:

```powershell
python -m unittest discover -s android/tools/ort-binding -v
```
