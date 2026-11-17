#!/usr/bin/env python3
"""Small synthetic input/flow tests; no native compilation or runtime experiment."""
import hashlib
import importlib.util
import io
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import warnings
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ort_builder", ROOT / "scripts/build-ort-native.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SmallBudget:
    def __init__(self, remaining=16 * module.MIB):
        self.remaining = remaining
        self.requests = []

    def check(self, additional=0):
        self.requests.append(additional)
        module.require(additional <= self.remaining, "synthetic budget exhausted")


class SourceInputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lantype-ort-input-test-")
        self.root = Path(self.temp.name)
        self.budget = SmallBudget()

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, entries):
        path = self.root / "source.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(path, "w") as archive:
                for name, content in entries:
                    archive.writestr(name, content)
        return path

    def test_extracts_sources_and_preserves_internal_link(self):
        path = self.archive([("source/", b""), ("source/lib/data.txt", b"exact content")])
        with zipfile.ZipFile(path, "a") as archive:
            link = zipfile.ZipInfo("source/lib/current")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "data.txt")
        out = self.root / "tree"
        module.safe_extract(path, out, self.budget)
        self.assertEqual((out / "lib/current").read_bytes(), b"exact content")
        self.assertTrue((out / "lib/current").is_symlink())

    def test_rejects_path_escape_before_creating_destination(self):
        for bad in ("source/../../escape", "/absolute", "C:/windows", "source\\escape"):
            with self.subTest(bad=bad):
                path = self.archive([(bad, b"payload")])
                out = self.root / "tree"
                with self.assertRaises(module.BuildError):
                    module.safe_extract(path, out, self.budget)
                self.assertFalse(out.exists())

    def test_rejects_duplicate_archive_members(self):
        path = self.archive([("source/file", b"first"), ("source/file", b"second")])
        with self.assertRaises(module.BuildError):
            module.safe_extract(path, self.root / "tree", self.budget)

    def test_rejects_escaping_link(self):
        path = self.archive([("source/", b"")])
        with zipfile.ZipFile(path, "a") as archive:
            link = zipfile.ZipInfo("source/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "../../outside")
        with self.assertRaises(module.BuildError):
            module.safe_extract(path, self.root / "tree", self.budget)

    def test_rejects_tar_special_files(self):
        path = self.root / "special.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            item = tarfile.TarInfo("source/device")
            item.type = tarfile.CHRTYPE
            archive.addfile(item)
        with self.assertRaises(module.BuildError):
            module.safe_extract(path, self.root / "tree", self.budget)

    def test_flat_gitiles_layout_and_official_dawn_test_omission(self):
        path = self.root / "flat.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name in ("LICENSE", "test/unused", "src/retained"):
                payload = name.encode()
                item = tarfile.TarInfo(name)
                item.size = len(payload)
                archive.addfile(item, io.BytesIO(payload))
        out = self.root / "tree"
        module.safe_extract(path, out, self.budget, flat=True, skip=("test",))
        self.assertTrue((out / "LICENSE").is_file())
        self.assertTrue((out / "src/retained").is_file())
        self.assertFalse((out / "test").exists())

    def test_never_overwrites_existing_source_tree(self):
        out = self.root / "tree"
        out.mkdir()
        (out / "user.txt").write_text("keep")
        with self.assertRaises(module.BuildError):
            module.safe_extract(self.archive([("source/file", b"new")]), out, self.budget)
        self.assertEqual((out / "user.txt").read_text(), "keep")

    def test_extraction_preflights_budget_before_writing(self):
        path = self.archive([("source/file", b"payload")])
        out = self.root / "tree"
        with self.assertRaises(module.BuildError):
            module.safe_extract(path, out, SmallBudget(1))
        self.assertFalse(out.exists())

    def test_stream_rejects_extra_and_truncated_bytes(self):
        for payload in (b"a", b"abcd"):
            with self.assertRaises(module.BuildError):
                module.copy_stream(io.BytesIO(payload), io.BytesIO(), self.budget, expected_size=3)

    def test_hash_mismatch_preserves_existing_archive(self):
        path = self.root / "source.bin"
        path.write_bytes(b"do not replace")
        with self.assertRaises(module.BuildError):
            module.obtain({"sha256": "0" * 64}, path, self.budget, download=True)
        self.assertEqual(path.read_bytes(), b"do not replace")

    def test_source_manifest_detects_modified_input(self):
        source = self.root / "src"
        source.mkdir()
        path = source / "normal.c"
        path.write_text("int answer = 1;\n")
        first = module.tree_manifest([source], self.root)
        path.write_text("int answer = 2;\n")
        self.assertNotEqual(first, module.tree_manifest([source], self.root))

    def test_hash_guard_rejects_changed_production_patch(self):
        path = self.root / "patch"
        path.write_bytes((ROOT / module.CPUINFO_PATCH).read_bytes() + b"\nchanged\n")
        with self.assertRaises(module.BuildError):
            module.verify_file(path, sha256=module.CPUINFO_PATCH_SHA)


class BuildContract(unittest.TestCase):
    def test_unbounded_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as value:
            with self.assertRaises(module.BuildError):
                module.Budget(Path(value))

    def test_budget_stops_before_space_or_inode_exhaustion(self):
        budget = module.Budget.__new__(module.Budget)
        budget.root = SimpleNamespace(stat=lambda: SimpleNamespace(st_dev=7))
        budget.device = 7
        budget.peak = 0
        good = {"capacityBytes": module.MAX_WORK_BYTES, "availableBytes": module.STOP_RESERVE + 1024,
                "usedBytes": 1024, "freeInodes": 8192}
        with mock.patch.object(module.os.path, "ismount", return_value=True):
            budget.sample = lambda: good
            budget.check(1024)
            for change in ({"availableBytes": module.STOP_RESERVE - 1}, {"freeInodes": 4095},
                           {"capacityBytes": module.MAX_WORK_BYTES + 1}):
                budget.sample = lambda change=change: {**good, **change}
                with self.assertRaises(module.BuildError):
                    budget.check()

    def test_fixed_four_provider_full_build_contract(self):
        obj = module.Builder.__new__(module.Builder)
        obj.work = Path("/bounded")
        obj.ort = obj.work / "src/runtime-onnxruntime"
        obj.dawn = obj.work / "src/ort-dawn"
        obj.cpuinfo = obj.work / "src/onnx-dependency-pytorch_cpuinfo"
        obj.sdk, obj.ndk, obj.cmake, obj.ninja = map(Path, ("/sdk", "/sdk/ndk/29.0.14206865", "/tools/cmake", "/tools/ninja"))
        obj.args = SimpleNamespace(jobs=2)
        command = obj.arguments()
        for flag in ("--use_nnapi", "--use_xnnpack", "--use_webgpu", "--enable_lto", "--build_shared_lib"):
            self.assertIn(flag, command)
        self.assertEqual(command[command.index("--use_webgpu") + 1], "static_lib")
        self.assertEqual(command[command.index("--android_api") + 1], "28")
        self.assertNotIn("--minimal_build", command)
        self.assertNotIn("--build_java", command)
        self.assertIn("onnxruntime_BUILD_UNIT_TESTS=OFF", command)
        self.assertIn("ANDROID_STL=c++_static", command)

    def test_download_requires_prepare_stage(self):
        args = ["--stage", "configure", "--work-root", "/bounded", "--sdk", "/sdk", "--ndk", "/ndk", "--cmake", "/cmake", "--download"]
        with self.assertRaises(module.BuildError):
            module.parse_arguments(args)

    def test_current_published_locks_and_production_patch_validate(self):
        obj = module.Builder.__new__(module.Builder)
        obj.base, obj.plan, obj.webgpu, obj.publication = [module.read_json(ROOT / p) for p in module.LOCK_FILES]
        obj.validate_locks()
        self.assertEqual(hashlib.sha256((ROOT / module.CPUINFO_PATCH).read_bytes()).hexdigest(), module.CPUINFO_PATCH_SHA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
