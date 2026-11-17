#!/usr/bin/env python3
"""Small ZIP-only regression checks; synthetic payloads are never executed."""
import importlib.util
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import warnings
import zipfile


sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("ort_runtime", Path(__file__).with_name("prepare-ort-runtime.py"))
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class RuntimeArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lantype-ort-zip-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.members = {
            "AndroidManifest.xml": b"manifest is preserved",
            "classes.jar": b"Java API is preserved",
            runtime.BRIDGE: b"JNI bridge is preserved",
            runtime.MEMBER: b"synthetic original payload",
            "headers/onnxruntime_c_api.h": b"header is preserved",
            "jni/": b"",
        }
        self.replacement = b"synthetic replacement payload, not an ELF"
        self.library = self.directory / "replacement.bin"
        self.library.write_bytes(self.replacement)

    def source(self, name="source.aar", reverse=False):
        path = self.directory / name
        with zipfile.ZipFile(path, "x") as archive:
            archive.comment = b"input metadata need not be reproduced"
            for member in sorted(self.members, reverse=reverse):
                info = zipfile.ZipInfo(member, (2020 if reverse else 2021, 2, 3, 4, 5, 6))
                info.compress_type = zipfile.ZIP_DEFLATED if reverse else zipfile.ZIP_STORED
                info.comment = b"metadata variant" if reverse else b""
                archive.writestr(info, self.members[member])
        return path

    def convert(self, source, prefix="result"):
        full, companion = (self.directory / f"{prefix}-{suffix}.aar" for suffix in ("full", "companion"))
        runtime.convert_aars(source, self.library, full, companion)
        return full, companion

    def test_only_runtime_changes_and_companion_omits_it(self):
        source = self.source()
        source_before = source.read_bytes()
        full, companion = self.convert(source)
        for path, expected in ((full, {**self.members, runtime.MEMBER: self.replacement}),
                               (companion, {name: data for name, data in self.members.items()
                                            if name != runtime.MEMBER})):
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(set(archive.namelist()), set(expected))
                for name, data in expected.items():
                    self.assertEqual(archive.read(name), data, name)
        self.assertEqual(source.read_bytes(), source_before)
        result = runtime.verify_aars(full, companion, runtime.file_identity(self.library))
        self.assertFalse(result["originalCompared"])

    def test_conversion_is_byte_deterministic_across_input_metadata(self):
        first = self.convert(self.source(), "first")
        second = self.convert(self.source("reordered.aar", reverse=True), "second")
        for left, right in zip(first, second):
            self.assertEqual(left.read_bytes(), right.read_bytes())
            with zipfile.ZipFile(left) as archive:
                self.assertEqual(archive.namelist(), sorted(archive.namelist()))
                self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist()))
                self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist()))

    def test_duplicate_members_are_rejected_even_with_identical_bytes(self):
        source = self.source()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(source, "a") as archive:
                archive.writestr("classes.jar", self.members["classes.jar"])
        with self.assertRaisesRegex(runtime.RuntimePackageError, "Duplicate ZIP member"):
            self.convert(source)

    def test_unsafe_names_and_symlinks_are_rejected(self):
        for number, name in enumerate(("../outside", "/absolute", "jni//empty", "jni/symlink")):
            with self.subTest(name=name):
                path = self.directory / f"invalid-{number}.zip"
                with zipfile.ZipFile(path, "x") as archive:
                    info = zipfile.ZipInfo(name)
                    if name.endswith("symlink"):
                        info.create_system = 3
                        info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(info, b"payload")
                with zipfile.ZipFile(path) as archive, self.assertRaises(runtime.RuntimePackageError):
                    runtime.archive_index(archive)

    def test_verification_rejects_changed_companion_java_member(self):
        full, companion = self.convert(self.source())
        altered = self.directory / "altered-companion.aar"
        with zipfile.ZipFile(companion) as original, zipfile.ZipFile(altered, "x") as output:
            for name in original.namelist():
                payload = b"unexpected Java replacement" if name == "classes.jar" else original.read(name)
                output.writestr(runtime.canonical_info(name), payload)
        with self.assertRaisesRegex(runtime.RuntimePackageError, "changed=\\['classes.jar'\\]"):
            runtime.verify_aars(full, altered, runtime.file_identity(self.library))


if __name__ == "__main__":
    unittest.main(verbosity=2)
