import io
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

from binding import JNI, RUNTIME, archive, binding_entries, deterministic_zip, symbols


class BindingTests(unittest.TestCase):
    def official_entries(self):
        classes = io.BytesIO()
        with zipfile.ZipFile(classes, "w") as z:
            z.writestr("ai/onnxruntime/OrtEnvironment.class", b"environment")
            z.writestr("ai/onnxruntime/OrtSession.class", b"session")
        return {"classes.jar": classes.getvalue(), "AndroidManifest.xml": b"manifest",
                "proguard.txt": b"consumer rules", JNI: b"java JNI", RUNTIME: b"runtime",
                "jni/x86/libonnxruntime.so": b"x86 runtime",
                "jni/x86/libonnxruntime4j_jni.so": b"x86 JNI",
                "jni/arm64-v8a/libprovider.so": b"provider"}

    def test_other_abis_and_all_runtime_binaries_are_removed_but_rules_preserved(self):
        original = self.official_entries()
        kept = binding_entries(original)
        self.assertEqual({n for n in kept if n.endswith(".so")}, {JNI})
        for name in ["classes.jar", "AndroidManifest.xml", "proguard.txt", JNI]:
            self.assertEqual(kept[name], original[name])

    def test_missing_java_api_is_rejected(self):
        entries = self.official_entries()
        entries["classes.jar"] = b"not a jar"
        with self.assertRaises(zipfile.BadZipFile):
            binding_entries(entries)

    def test_duplicate_zip_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "duplicate.aar"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(file, "w") as z:
                    z.writestr(RUNTIME, b"first")
                    z.writestr(RUNTIME, b"second")
            with self.assertRaisesRegex(ValueError, "Duplicate ZIP"):
                archive(file)

    def test_identical_input_gives_identical_archive_regardless_of_order(self):
        entries = binding_entries(self.official_entries())
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.aar", Path(tmp) / "b.aar"
            deterministic_zip(entries, a)
            deterministic_zip(dict(reversed(list(entries.items()))), b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(archive(a), entries)

    def test_readelf_parser_distinguishes_versioned_import_and_export(self):
        rows = symbols("""
  7: 0000000000000000 0 FUNC GLOBAL DEFAULT UND OrtGetApiBase@VERS_1.27.0 (2)
  8: 000000000000abcd 12 FUNC GLOBAL DEFAULT 15 OrtGetApiBase@@VERS_1.27.1
""")
        self.assertEqual(rows, [("OrtGetApiBase", "VERS_1.27.0", True),
                                ("OrtGetApiBase", "VERS_1.27.1", False)])


if __name__ == "__main__":
    unittest.main()
