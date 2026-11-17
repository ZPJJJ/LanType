#!/usr/bin/env python3
"""Restore only 399 current-lock inputs from the fixed, previously published ZIP.

Existing valid files are retained; conflicts and symlink paths are rejected.
Downloads require --download. No SDK, compiler, Gradle or native code is run.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import sys
from urllib.request import Request, build_opener
import zipfile

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


transfer = module("ort_transfer", "restore-ort-runtime.py")
runtime = transfer.runtime
resources = module("commercial_resources", "verify-commercial-resources.py")
ROOT = SCRIPTS.parent
PREFIX = "LanType-1.1.0/"
URL = "https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/LanType-1.1.0-runtime-dependencies.zip"
ARCHIVE = {"bytes": 139297354, "sha256": "42a0e57c002662e2a502719a7f002b061fd49605d92a87cab221bf6d9aa922bc"}
CACHE = ROOT / ".gradle/base-runtime-archives" / (ARCHIVE["sha256"] + ".zip")
RESERVE = 256 * runtime.CHUNK
LOCKS = ("resources.lock.json", "native-prebuilt.lock.json", "camerax-rebuilt.lock.json")
IGNORED = {"LICENSE", "RUNTIME-DEPENDENCIES-INVENTORY.json", *("docs/licensing/" + name for name in LOCKS)}


@contextmanager
def parent_fd(path, create=False):
    """Traverse every parent with O_NOFOLLOW, including parents of the repository."""
    path = Path(path).absolute()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:-1]:
            if create:
                try:
                    os.mkdir(part, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def inspect_file(descriptor, name, expected):
    try:
        handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
    except FileNotFoundError:
        return False
    with os.fdopen(handle, "rb") as stream:
        info = os.fstat(stream.fileno())
        runtime.require(stat.S_ISREG(info.st_mode) and info.st_size == expected["bytes"],
                        f"Existing file has wrong type/size; preserved: {name}")
        runtime.match(runtime.stream_identity(stream), expected, name)
    return True


def present(path, expected):
    try:
        with parent_fd(path) as descriptor:
            return inspect_file(descriptor, Path(path).name, expected)
    except FileNotFoundError:
        return False


def safe_relative(name):
    runtime.require(isinstance(name, str) and name and not name.startswith("/")
                    and "\\" not in name and ":" not in name
                    and all(part not in ("", ".", "..") for part in name.split("/"))
                    and not any(ord(char) < 32 or ord(char) == 127 for char in name),
                    f"Unsafe locked path: {name!r}")
    return name


def load_inputs():
    locks, hashes, records = [], {}, {}
    for filename in LOCKS:
        path = ROOT / "docs/licensing" / filename
        with parent_fd(path) as descriptor:
            with os.fdopen(os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor), "rb") as stream:
                info = os.fstat(stream.fileno())
                runtime.require(stat.S_ISREG(info.st_mode) and info.st_size <= runtime.CHUNK, "Invalid lock file")
                data = stream.read(runtime.CHUNK + 1)
        locks.append(json.loads(data, object_pairs_hook=runtime.unique_object))
        hashes[filename] = hashlib.sha256(data).hexdigest()
    resource_lock, native_lock, camera_lock = locks
    groups = [("assets", resource_lock["resources"], 379), ("raw", resource_lock["rawResources"], 11),
              ("native", native_lock["files"], 7), ("camera", camera_lock["outputs"], 2)]
    for kind, entries, count in groups:
        runtime.require(len(entries) == count, f"Unexpected {kind} lock count")
        for entry in entries:
            relative = safe_relative(entry["path"])
            if kind == "assets":
                relative = "app/src/main/assets/" + relative
            elif kind == "raw":
                relative = resources.raw_path(entry).relative_to(resources.ROOT).as_posix()
                runtime.require(relative.startswith("app/src/main/res/raw/"), "Unexpected raw destination")
            elif kind == "native":
                runtime.require(relative.startswith(("jniLibs/arm64-v8a/", "java/")), "Unexpected native destination")
                relative = "vendor/cyime-1.15.94/" + relative
            else:
                runtime.require(relative in {"vendor/lantype-camerax-native/arm64-v8a/" + name for name in (
                    "libimage_processing_util_jni.so", "libsurface_util_jni.so")}, "Unexpected CameraX destination")
            safe_relative(relative)
            runtime.require(relative not in records, "Duplicate locked destination: " + relative)
            records[relative] = {**runtime.identity({"bytes": entry["size"], "sha256": entry["sha256"]}, relative), "group": kind}
    runtime.require(len(records) == 399, "Expected exactly 399 base runtime inputs")
    return records, hashes


class LimitedReader:
    def __init__(self, stream, limit):
        self.stream, self.remaining = stream, limit

    def read(self, size):
        data = self.stream.read(min(size, self.remaining + 1))
        runtime.require(len(data) <= self.remaining, "Input exceeds the locked byte count")
        self.remaining -= len(data)
        return data


def install(path, expected, incoming):
    """Install a fresh inode atomically, without replacing a concurrent user's file."""
    with parent_fd(path, create=True) as descriptor:
        if inspect_file(descriptor, path.name, expected):
            return False
        temporary = ".base-runtime-" + secrets.token_hex(12) + ".tmp"
        handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=descriptor)
        try:
            with os.fdopen(handle, "wb") as outgoing:
                runtime.match(runtime.stream_identity(LimitedReader(incoming, expected["bytes"]), [outgoing]), expected, str(path))
            try:
                os.link(temporary, path.name, src_dir_fd=descriptor, dst_dir_fd=descriptor, follow_symlinks=False)
                return True
            except FileExistsError:
                runtime.require(inspect_file(descriptor, path.name, expected), "Destination changed during installation")
                return False
        finally:
            os.unlink(temporary, dir_fd=descriptor)


def restore(root, records, archive=None, download=False, verify_only=False):
    existing = {name for name, expected in records.items() if present(root / name, expected)}
    missing = sorted(set(records) - existing)
    runtime.require(not verify_only or not missing, "Missing base inputs: " + ", ".join(missing))
    result = {"verifiedFiles": len(records), "preservedFiles": len(existing), "restoredFiles": 0,
              "archiveVerified": False, "downloadPerformed": False,
              "countsByGroup": {kind: sum(entry["group"] == kind for entry in records.values())
                                for kind in ("assets", "raw", "native", "camera")}}
    if verify_only or not missing and archive is None:
        return {**result, "files": [{"path": name, **expected} for name, expected in sorted(records.items())]}
    needed = sum(records[name]["bytes"] for name in missing)
    peak = needed + max((records[name]["bytes"] for name in missing), default=0) + ARCHIVE["bytes"]
    runtime.require(peak < 5 * runtime.GIB and shutil.disk_usage(root).free >= peak + RESERVE,
                    "Insufficient space/budget for restoration plus a 256 MiB reserve")
    if archive is None:
        archive = CACHE
        if not present(archive, ARCHIVE):
            runtime.require(download, "Missing archive; use --archive FILE or explicitly allow --download")
            request = Request(URL, headers={"User-Agent": "LanType-base-runtime-restorer", "Accept-Encoding": "identity"})
            with build_opener(transfer.ReleaseRedirect()).open(request, timeout=60) as response:
                install(archive, ARCHIVE, response)
            result["downloadPerformed"] = True
    runtime.require(present(archive, ARCHIVE), "Missing fixed runtime ZIP")
    with zipfile.ZipFile(archive) as source:
        index = runtime.archive_index(source)
        runtime.require(set(index) == {PREFIX + name for name in set(records) | IGNORED}, "Unexpected base ZIP inventory")
        # Validate every required member before installing any file, including already-present inputs.
        for name, expected in records.items():
            info = index[PREFIX + name]
            runtime.require(not info.is_dir() and info.file_size == expected["bytes"], "Wrong member size/type: " + name)
            runtime.match(runtime.member_identity(source, info), expected, name)
        for name in missing:
            with source.open(index[PREFIX + name]) as incoming:
                result["restoredFiles"] += install(root / name, records[name], incoming)
    runtime.require(present(archive, ARCHIVE), "Runtime ZIP changed during restoration")
    for name, expected in records.items():
        runtime.require(present(root / name, expected), "Input disappeared: " + name)
    result.update({"archiveVerified": True, "archive": ARCHIVE, "ignoredArchiveMembers": sorted(IGNORED),
                   "preservedFiles": len(records) - result["restoredFiles"],
                   "files": [{"path": name, **expected} for name, expected in sorted(records.items())]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--archive", type=Path, help="Local fixed runtime-dependencies ZIP")
    inputs.add_argument("--download", action="store_true", help="Explicitly permit the fixed public release download")
    parser.add_argument("--verify-only", action="store_true", help="Verify all local inputs without restoring or downloading")
    parser.add_argument("--receipt", type=Path, help="Write a new JSON receipt; never overwrite an existing file")
    args = parser.parse_args()
    if args.verify_only and (args.archive or args.download):
        parser.error("--verify-only cannot be combined with --archive or --download")
    records, hashes = load_inputs()
    result = restore(ROOT, records, args.archive, args.download, args.verify_only)
    runtime.require(load_inputs()[1] == hashes, "Source locks changed during verification")
    result.update({"schemaVersion": 1, "kind": "lantype-base-runtime-receipt", "ok": True,
                   "lockSha256": hashes, "nativeCodeExecuted": False, "runtimeAcceptancePerformed": False})
    data = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if args.receipt:
        runtime.require(not args.receipt.exists() and not args.receipt.is_symlink(), "Receipt already exists")
        install(args.receipt, {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}, io.BytesIO(data))
    sys.stdout.buffer.write(data)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, zipfile.BadZipFile, EOFError, KeyError, TypeError) as error:
        print(json.dumps({"ok": False, "error": str(error), "nativeCodeExecuted": False}), file=sys.stderr)
        sys.exit(1)
