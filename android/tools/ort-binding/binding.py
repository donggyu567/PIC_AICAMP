"""Fail-closed ELF validation and deterministic binding-only AAR packaging."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
LOCK = json.loads((HERE / "source-lock.json").read_text())
ABI = "arm64-v8a"
JNI = f"jni/{ABI}/libonnxruntime4j_jni.so"
RUNTIME = f"jni/{ABI}/libonnxruntime.so"
SHERPA = f"jni/{ABI}/libsherpa-onnx-jni.so"
VERSION = "VERS_1.27.1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archive(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        require(len(names) == len(set(names)), f"Duplicate ZIP entries: {path}")
        return {n: z.read(n) for n in names if not n.endswith("/")}


def symbols(output):
    result = []
    for line in output.splitlines():
        cols = line.split()
        if len(cols) < 8 or not re.fullmatch(r"\d+:", cols[0]):
            continue
        raw = cols[7]
        name, _, version = raw.replace("@@", "@").partition("@")
        result.append((name, version, cols[6] == "UND"))
    return result


def elf(readelf, data, name, directory):
    require(data[:6] == b"\x7fELF\x02\x01", f"Not ELF64 little endian: {name}")
    require(int.from_bytes(data[18:20], "little") == 183, f"Not ARM64: {name}")
    file = directory / name
    file.write_bytes(data)
    outputs = {}
    for label, args in {
        "dynamic": ["--dynamic"], "symbols": ["--dyn-syms"],
        "versions": ["--version-info"], "segments": ["--program-headers"],
    }.items():
        cmd = [str(readelf), "--wide", *args, str(file)]
        text = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="strict")
        outputs[label] = {"command": cmd, "output": text}
    return {
        "sha256": digest(data),
        "needed": re.findall(r"\(NEEDED\).*?\[([^\]]+)\]", outputs["dynamic"]["output"]),
        "symbols": symbols(outputs["symbols"]["output"]),
        "readelf": outputs,
    }


def verify_elf(sherpa_path, java_bytes, readelf, evidence_path=None):
    require(digest(sherpa_path.read_bytes()) == LOCK["sherpaAarSha256"], "Unexpected sherpa AAR")
    old = archive(sherpa_path)
    require(digest(old[RUNTIME]) == LOCK["runtimeSha256"], "Unexpected sherpa runtime")
    with tempfile.TemporaryDirectory(prefix="ort-elf-") as tmp:
        directory = Path(tmp)
        runtime = elf(readelf, old[RUNTIME], "libonnxruntime.so", directory)
        sherpa = elf(readelf, old[SHERPA], "libsherpa-onnx-jni.so", directory)
        java = elf(readelf, java_bytes, "libonnxruntime4j_jni.so", directory) if java_bytes is not None else None
    evidence = {"runtime": runtime, "sherpa": sherpa, "java": java}
    if evidence_path:
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")
    exports = {(n, v) for n, v, undefined in runtime["symbols"] if not undefined}
    require(("OrtGetApiBase", VERSION) in exports, "Runtime does not export OrtGetApiBase@VERS_1.27.1")
    for name, info in [("sherpa", sherpa)] + ([("java", java)] if java else []):
        require("libonnxruntime.so" in info["needed"], f"{name}: missing runtime DT_NEEDED")
        imports = {(n, v) for n, v, undefined in info["symbols"] if undefined and n.startswith("Ort")}
        require(("OrtGetApiBase", VERSION) in imports, f"{name}: requires wrong OrtGetApiBase version: {sorted(imports)}")
        require(imports <= exports, f"{name}: unsatisfied ORT imports: {sorted(imports - exports)}")
        require(not any(n == "OrtGetApiBase" and not u for n, v, u in info["symbols"]), f"{name}: embedded runtime")
    return evidence


def binding_entries(entries):
    require("classes.jar" in entries and "AndroidManifest.xml" in entries, "Missing AAR classes/manifest")
    require(JNI in entries and RUNTIME in entries, "Expected official ARM64 AAR with JNI and runtime")
    with zipfile.ZipFile(io.BytesIO(entries["classes.jar"])) as jar:
        require("ai/onnxruntime/OrtEnvironment.class" in jar.namelist(), "Missing ORT Java API")
        require("ai/onnxruntime/OrtSession.class" in jar.namelist(), "Missing ORT session API")
    # Preserve metadata, manifest, consumer rules and Java classes byte for byte.
    # No other ABI, provider or runtime native binary can survive this allowlist.
    return {n: data for n, data in entries.items()
            if n == JNI or (not n.startswith("jni/") and not n.endswith((".so", ".a")))}


def deterministic_zip(entries, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as z:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)


def package(full, receipt_path, sherpa, readelf, output):
    receipt = json.loads(receipt_path.read_text())
    require(receipt["commit"] == LOCK["commit"] and receipt["tag"] == LOCK["tag"], "Wrong source receipt")
    require(receipt["aarSha256"] == digest(full.read_bytes()), "AAR does not match official build receipt")
    require(receipt["settingsSha256"] == digest((HERE / "arm64-cpu.json").read_bytes()), "Build settings differ from receipt")
    entries = archive(full)
    evidence = verify_elf(sherpa, entries[JNI], readelf, output.with_suffix(".elf-evidence.json"))
    kept = binding_entries(entries)
    require([n for n in kept if n.endswith(".so")] == [JNI], "Unexpected binding native payload")
    deterministic_zip(kept, output)
    report = {"source": receipt, "bindingSha256": digest(output.read_bytes()),
              "entries": sorted(kept), "elf": evidence}
    output.with_suffix(".verification.json").write_text(json.dumps(report, indent=2) + "\n")
    output.with_suffix(".aar.sha256").write_text(f"{report['bindingSha256']}  {output.name}\n")
    return report


def verify_apk(apk, sherpa, binding, readelf):
    entries = archive(apk)
    old, new = archive(sherpa), archive(binding)
    expected = {
        "libonnxruntime.so": old[RUNTIME],
        "libonnxruntime4j_jni.so": new[JNI],
        "libsherpa-onnx-jni.so": old[SHERPA],
        "libsherpa-onnx-c-api.so": old[f"jni/{ABI}/libsherpa-onnx-c-api.so"],
        "libsherpa-onnx-cxx-api.so": old[f"jni/{ABI}/libsherpa-onnx-cxx-api.so"],
    }
    require(not any(n.startswith("lib/") and not n.startswith(f"lib/{ABI}/") for n in entries), "Unexpected APK ABI")
    for name, data in expected.items():
        matches = [n for n in entries if n.endswith("/" + name)]
        require(matches == [f"lib/{ABI}/{name}"], f"Expected exactly one {name}, got {matches}")
        # Do not silently accept a replaced runtime. If AGP strips an input,
        # investigate the difference rather than weakening this provenance check.
        require(entries[matches[0]] == data, f"APK bytes differ from supplying AAR: {name}")
    evidence = verify_elf(sherpa, entries[f"lib/{ABI}/libonnxruntime4j_jni.so"], readelf)
    return {"apkSha256": digest(apk.read_bytes()), "nativeEntries": sorted(n for n in entries if n.startswith("lib/")), "elf": evidence}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("audit-elf")
    for arg in ("sherpa", "readelf", "report"):
        p.add_argument("--" + arg, type=Path, required=True)
    p.add_argument("--java-so", type=Path)
    p = commands.add_parser("package")
    for arg in ("full-aar", "receipt", "sherpa", "readelf", "output"):
        p.add_argument("--" + arg, type=Path, required=True)
    p = commands.add_parser("verify-apk")
    for arg in ("apk", "sherpa", "binding", "readelf", "report"):
        p.add_argument("--" + arg, type=Path, required=True)
    args = parser.parse_args()
    if args.command == "audit-elf":
        verify_elf(args.sherpa, args.java_so.read_bytes() if args.java_so else None, args.readelf, args.report)
        print("ELF validation passed" + (" (sherpa only; Java JNI not tested)" if not args.java_so else ""))
    elif args.command == "package":
        result = package(args.full_aar, args.receipt, args.sherpa, args.readelf, args.output)
        print("Verified binding SHA-256:", result["bindingSha256"])
    else:
        result = verify_apk(args.apk, args.sherpa, args.binding, args.readelf)
        args.report.write_text(json.dumps(result, indent=2) + "\n")
        print("Verified APK:", result["nativeEntries"])


if __name__ == "__main__":
    main()
