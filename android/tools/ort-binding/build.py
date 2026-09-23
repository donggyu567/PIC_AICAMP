"""Build the exact upstream Android AAR; validate before emitting a binding AAR.

Requires Python 3.11, Git, JDK 17/21, Android SDK 34, the locked NDK/CMake,
and network access for upstream dependencies. Does not edit the app's Gradle file.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import urllib.request

from binding import HERE, LOCK, digest, package, require

ROOT = HERE.parents[2]


def run(command, *, cwd=None, env=None):
    command = list(map(str, command))
    print("RUN", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def build(args):
    work = args.work_dir.resolve()
    source = work / "onnxruntime"
    work.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        run(["git", "clone", "--depth", "1", "--branch", LOCK["tag"], LOCK["repository"], source])
    require(git(source, "rev-parse", "HEAD") == LOCK["commit"], "ORT HEAD differs from source lock")
    require(git(source, "rev-parse", LOCK["tag"] + "^{commit}") == LOCK["commit"], "ORT tag differs from source lock")
    require(not git(source, "status", "--porcelain", "--untracked-files=no"), "ORT source has tracked modifications")
    require((source / "VERSION_NUMBER").read_text().strip() == "1.27.1", "Wrong ORT version")
    run(["git", "-C", source, "submodule", "update", "--init", "--recursive"])

    sdk = args.android_sdk.resolve()
    ndk = sdk / "ndk" / LOCK["ndk"]
    cmake_bin = sdk / "cmake" / LOCK["cmake"] / "bin"
    suffix = ".exe" if os.name == "nt" else ""
    host = "windows-x86_64" if os.name == "nt" else ("darwin-x86_64" if sys.platform == "darwin" else "linux-x86_64")
    readelf = ndk / "toolchains/llvm/prebuilt" / host / "bin" / ("llvm-readelf" + suffix)
    for file in [readelf, cmake_bin / ("cmake" + suffix), cmake_bin / ("ninja" + suffix),
                 sdk / "platforms/android-34/android.jar"]:
        require(file.is_file(), f"Missing prerequisite: {file}")
    require(f"Pkg.Revision = {LOCK['ndk']}" in (ndk / "source.properties").read_text(), "NDK revision mismatch")
    env = os.environ.copy()
    require(env.get("JAVA_HOME"), "Set JAVA_HOME to JDK 17 or 21")
    env["PATH"] = os.pathsep.join([str(cmake_bin), str(Path(env["JAVA_HOME"]) / "bin"), str(Path(sys.executable).parent), env.get("PATH", "")])
    env["ANDROID_HOME"] = str(sdk)
    env["ANDROID_NDK_HOME"] = str(ndk)
    env["GRADLE_USER_HOME"] = str(work / "gradle-home")
    env["PYTHONUTF8"] = "1"
    env["RELEASE_VERSION_SUFFIX"] = ""
    java_version = subprocess.check_output(
        [str(Path(env["JAVA_HOME"]) / "bin" / ("java" + suffix)), "-version"],
        stderr=subprocess.STDOUT,
        text=True,
    )
    command = [sys.executable, source / "tools/ci_build/github/android/build_aar_package.py",
               "--android_sdk_path", sdk, "--android_ndk_path", ndk,
               "--build_dir", work / "aar-build", "--config", "Release", HERE / "arm64-cpu.json"]
    if args.package_existing:
        native_dir = work / "aar-build/intermediates/arm64-v8a/Release"
        jni_dir = work / "aar-build/intermediates/jnilibs/Release/arm64-v8a"
        jni_dir.mkdir(parents=True, exist_ok=True)
        for name in ["libonnxruntime.so", "libonnxruntime4j_jni.so"]:
            require((native_dir / name).is_file(), f"Missing completed native output: {native_dir / name}")
            shutil.copyfile(native_dir / name, jni_dir / name)
        gradle = source / "java/gradlew.bat" if os.name == "nt" else source / "java/gradlew"
        gradle_args = [gradle, "--no-daemon"]
        if 'version "21' in java_version:
            gradle_args.extend(["-I", HERE / "android-jdk21.init.gradle"])
        gradle_args.extend(["-b=build-android.gradle", "-c=settings-android.gradle",
                       f"-DjniLibsDir={jni_dir.parent}",
                       f"-DbuildDir={work / 'aar-build/intermediates/aar/Release'}",
                       f"-DheadersDir={native_dir / 'android/headers'}",
                       f"-DpublishDir={work / 'aar-build/aar_out/Release'}",
                       "-DminSdkVer=24", "-DtargetSdkVer=34", "-DENABLE_TRAINING_APIS=0",
                       "-DreleaseVersionSuffix="])
        for task in ["clean", "build", "publish"]:
            run([*gradle_args, task], cwd=source / "java", env=env)
        command = [*command, "[native build already completed; official Gradle package resumed after Windows symlink failure]"]
    else:
        run(command, cwd=source, env=env)
    require(not git(source, "diff", "--name-only"), "Official build modified tracked source; inspect before packaging")
    candidates = list((work / "aar-build/aar_out/Release").rglob("onnxruntime-android-1.27.1.aar"))
    require(len(candidates) == 1, f"Expected one official v1.27.1 AAR, found {candidates}")
    full = candidates[0]
    receipt = {
        "tag": LOCK["tag"], "commit": LOCK["commit"], "repository": LOCK["repository"],
        "aarSha256": digest(full.read_bytes()), "settingsSha256": digest((HERE / "arm64-cpu.json").read_bytes()),
        "command": list(map(str, command)), "python": sys.version, "host": platform.platform(),
        "ndk": LOCK["ndk"], "cmake": LOCK["cmake"],
        "submodules": git(source, "submodule", "status", "--recursive"),
        "javaVersion": java_version,
    }
    receipt_path = work / "official-aar-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    # No artifact is copied into app/libs before all ELF checks pass.
    output = work / "artifacts/onnxruntime-java-binding-1.27.1-arm64.aar"
    report = package(full, receipt_path, ROOT / "android/app/libs/sherpa-onnx-1.13.6.aar", readelf, output)
    print("VERIFIED", output, report["bindingSha256"])


def model(args):
    lock = LOCK["model"]
    url = f"https://huggingface.co/{lock['repository']}/resolve/{lock['revision']}/{lock['file']}"
    data = urllib.request.urlopen(url, timeout=120).read()
    require(digest(data) == lock["sha256"], "NER model checksum mismatch")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print("Verified FP32 model", args.output, lock["sha256"])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)
    b = commands.add_parser("build")
    b.add_argument("--android-sdk", type=Path, required=True)
    b.add_argument("--work-dir", type=Path, default=ROOT / ".runtime-build")
    b.add_argument("--package-existing", action="store_true",
                   help="Resume official Gradle AAR packaging from completed native outputs on hosts without symlink privilege")
    m = commands.add_parser("model")
    m.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.command == "build":
        build(args)
    else:
        model(args)


if __name__ == "__main__":
    main()
