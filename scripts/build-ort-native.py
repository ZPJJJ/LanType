#!/usr/bin/env python3
"""Stage a pinned Android ORT build inside an exclusive, size-limited filesystem.

This is an ordinary production build entry point. It does not run host memory
experiments, Android programs, tests, Java packaging, or APK integration.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
MIB = 1024**2
GIB = 1024**3
MAX_WORK_BYTES = 4608 * MIB
STOP_RESERVE = 256 * MIB
MAX_LOG_BYTES = 64 * MIB
ORT_COMMIT = "da9b5e364c465de65c49d91e696cd6485270757f"
DAWN_COMMIT = "ec7b457e5bb1fcec6f59733c4f3dd84d2f885a38"
NDK_VERSION = "29.0.14206865"
CMAKE_VERSION = "3.31.6"
CPUINFO_COMMIT = "4628dc060ce4e82345dc166bbac875609db4ff69"
CPUINFO_PATCH = "patches/onnxruntime/cpuinfo-4628dc0-pr457-l2-backport.patch"
CPUINFO_PATCH_SHA = "6281246ef5bafdae6f64a9b1c4bbd64ddcd6b0b65a8150c9bd0343e3cfdf998b"
CPUINFO_BEFORE = "daaf6633d55c983e9b517d748d1fdf3df580c6c8bef03e4fd3811ba47f175e4f"
CPUINFO_AFTER = "94a7bd19139090a0568e173f80dea5e42ea1326d04e3eddf46554f5243e5229c"
# The seven original ORT Dawn patches use GNU patch's default maximum fuzz 2.
# These exact before/after identities were checked, in order, against the
# locked Dawn archive; they keep contextual fuzz from accepting another file.
DAWN_PATCH_TARGETS = {
    "dawn-1": ("third_party/emdawnwebgpu/pkg/webgpu/src/webgpu.cpp",
               "4473a7d401dc3f73298c2a4256cccf00fa99c01b108aa0b20e36c3ce2a172677",
               "c92fe981b7e5e344f2222c8bf7b42d57934331e25bf0d8b3218ada206f5ebacd"),
    "dawn-2": ("src/tint/CMakeLists.txt",
               "649084e2eab11044de97cfb480104b43a03232b2eae56a20d64fca7fb547b56a",
               "21130a04f2a8bca2c293587826b4f9a18f38688a2307b6f6eb5b55f83393cb47"),
    "dawn-3": ("third_party/emdawnwebgpu/pkg/webgpu/src/library_webgpu.js",
               "54b3bb8228f8eeafb514f0aad6a72abf8b68ca23864d17897962d51219565897",
               "25c26d17b01e027935481c09c8a9ba29b9aa091444e0e3279a67db50d89835ab"),
    "dawn-4": ("third_party/emdawnwebgpu/pkg/webgpu/src/library_webgpu.js",
               "25c26d17b01e027935481c09c8a9ba29b9aa091444e0e3279a67db50d89835ab",
               "eb17c62ecb80e3b1c1b533b28394c8602d98c6cfcb5b853fef0a4ab0ac9a3685"),
    "dawn-5": ("third_party/CMakeLists.txt",
               "316f7da1a4ca75782faf5193edad8ee8b4d29e20954228aa7f9fe7663b7a22a6",
               "45181fdf8d092fc07218ccd8c83fd3bbc77f75493f5d275634d89f93f16862ee"),
    "dawn-6": ("third_party/emdawnwebgpu/pkg/webgpu/src/webgpu.cpp",
               "c92fe981b7e5e344f2222c8bf7b42d57934331e25bf0d8b3218ada206f5ebacd",
               "f44d107a978dcd61f0189d0ff41e2f2c49fa190e426a1b4eb1754d0218ba48d7"),
    "dawn-7": ("src/emdawnwebgpu/CMakeLists.txt",
               "7164e1167e66ef1749f5dbb91ad49e0ffd8b70d2ed67c69c6d3da4b6ca9faab9",
               "44c523a51dd57187a1b6221ad0f18c18a2dabcfadcb59da7b9cae67f8e942aeb"),
}
SUPPLEMENT_SHA = "6eabae67a60bdb0f3eaab9858f58b1f712edb9f85bb4c5cf75d800e7f530691d"
SUPPLEMENT_BYTES = 105554498
SUPPLEMENT_NAME = "LanType-native-source-webgpu-supplement-v1"
LOCK_FILES = (
    "docs/licensing/native-sources.lock.json",
    "docs/licensing/dawn-source-plan.json",
    "docs/licensing/native-sources-webgpu.lock.json",
    "docs/licensing/dawn-source-publication.json",
)
# Fixed Android/full/native-only branch, read from this ORT commit's CMake files.
# Values are FetchContent project names, which determine _deps/<name>-src.
DEPS = {
    "abseil_cpp": "abseil_cpp", "re2": "re2", "protobuf": "protobuf",
    "date": "date", "mp11": "mp11", "json": "nlohmann_json",
    "pytorch_cpuinfo": "pytorch_cpuinfo", "microsoft_gsl": "gsl",
    "safeint": "safeint", "flatbuffers": "flatbuffers", "onnx": "onnx",
    "eigen": "eigen3", "fxdiv": "fxdiv", "pthreadpool": "pthreadpool",
    "kleidiai": "kleidiai", "googlexnnpack": "googlexnnpack",
}


class BuildError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise BuildError(message)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def file_hash(path, algorithm="sha256"):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path):
    require(path.is_file() and not path.is_symlink(), "Expected regular JSON: " + str(path))
    require(path.stat().st_size < 32 * MIB, "Oversized JSON: " + str(path))
    return json.loads(path.read_text(), object_pairs_hook=unique_keys)


def write_json(path, value):
    temporary = path.with_name(path.name + ".writing")
    require(not temporary.is_symlink(), "Refusing symlink JSON temporary")
    with temporary.open("wb") as stream:
        stream.write(json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def contained(path, root):
    return path.resolve().is_relative_to(root.resolve())


def clean_relative(value):
    require(isinstance(value, str) and value and len(value) < 4096, "Invalid member path")
    require(not any(ord(c) < 32 or ord(c) == 127 for c in value), "Control character in path")
    require("\\" not in value and ":" not in value and not value.startswith("/"), "Absolute/Windows member path")
    while value.startswith("./"):
        value = value[2:]
    value = value.rstrip("/")
    if value in ("", "."):
        return ""
    parts = value.split("/")
    require(all(p not in ("", ".", "..") for p in parts), "Unsafe archive path: " + value)
    return "/".join(parts)


def safe_link(relative, target):
    require(target and not target.startswith("/") and "\\" not in target and ":" not in target,
            "Unsafe archive link")
    require(not any(ord(c) < 32 or ord(c) == 127 for c in target), "Control character in link")
    parts = list(PurePosixPath(relative).parent.parts)
    for piece in target.split("/"):
        if piece == "..":
            require(parts, "Archive link escapes source tree")
            parts.pop()
        elif piece not in ("", "."):
            parts.append(piece)
    require(parts, "Archive link points to source root")
    return target


class Budget:
    """The filesystem is the hard cap; statvfs polling provides an early stop."""

    def __init__(self, root):
        require(sys.platform == "linux", "This entry point requires a Linux runner")
        require(root.is_dir() and not root.is_symlink(), "Work root must already exist and be a real mount point")
        require(root == root.resolve() and os.path.ismount(root), "Work root must be an absolute exclusive mount root")
        require(root.stat().st_dev != root.parent.stat().st_dev, "A bind directory is not a separate budget filesystem")
        self.root = root
        self.device = root.stat().st_dev
        self.initial = self.sample()
        require(512 * MIB <= self.initial["capacityBytes"] <= MAX_WORK_BYTES,
                "Work filesystem capacity must be between 512 MiB and 4608 MiB; no unbounded fallback")
        self.peak = self.initial["usedBytes"]
        self.check()

    def sample(self):
        info = os.statvfs(self.root)
        return {"capacityBytes": info.f_blocks * info.f_frsize,
                "usedBytes": (info.f_blocks - info.f_bfree) * info.f_frsize,
                "availableBytes": info.f_bavail * info.f_frsize,
                "freeInodes": info.f_favail}

    def check(self, additional=0):
        require(self.root.stat().st_dev == self.device and os.path.ismount(self.root), "Budget mount changed")
        item = self.sample()
        self.peak = max(getattr(self, "peak", 0), item["usedBytes"])
        require(item["capacityBytes"] <= MAX_WORK_BYTES, "Budget filesystem was expanded")
        require(item["availableBytes"] >= STOP_RESERVE + additional,
                "Budget stop: less than 256 MiB safety reserve plus pending allocation")
        require(item["freeInodes"] >= 4096, "Budget stop: fewer than 4096 free inodes")
        return item

    def receipt(self):
        return {**self.sample(), "peakObservedUsedBytes": self.peak,
                "hardCapacityLimitBytes": MAX_WORK_BYTES, "stopReserveBytes": STOP_RESERVE,
                "taskBudgetBytes": 5 * GIB, "outsideMountReservationBytes": 512 * MIB,
                "outsideMountBudgetCheck": "workflow-checkpoints-not-filesystem-quota",
                "wholeTaskFiveGiBHardEnforced": False}


def verify_file(path, size=None, sha256=None, sha1=None):
    require(path.is_file() and not path.is_symlink(), "Missing regular input: " + str(path))
    if size is not None:
        require(path.stat().st_size == size, "Input size mismatch: " + path.name)
    actual = file_hash(path)
    if sha256:
        require(actual == sha256, "SHA-256 mismatch: " + path.name)
    if sha1:
        require(file_hash(path, "sha1") == sha1, "Upstream SHA-1 mismatch: " + path.name)
    return {"bytes": path.stat().st_size, "sha256": actual, "sha1": sha1}


def copy_stream(stream, target, budget, expected_size=None, maximum=384 * MIB):
    count = 0
    while True:
        chunk = stream.read(MIB)
        if not chunk:
            break
        count += len(chunk)
        require(count <= maximum and (expected_size is None or count <= expected_size), "Input exceeds approved size")
        budget.check(len(chunk) + 4096)
        target.write(chunk)
    if expected_size is not None:
        require(count == expected_size, "Truncated input")
    return count


def safe_extract(archive_path, destination, budget, *, flat=False, skip=()):
    """Extract bounded regular files and internal symlinks; never use extractall.

    The destination must be new. Interrupted staging is preserved and rejected
    on the next attempt, rather than silently deleting potentially edited files.
    """
    require(not destination.exists() and not destination.is_symlink(), "Preserving existing extraction tree: " + str(destination))
    records, seen = [], set()
    with contextlib.ExitStack() as stack:
        is_zip = zipfile.is_zipfile(archive_path)
        archive = stack.enter_context(zipfile.ZipFile(archive_path) if is_zip else tarfile.open(archive_path, "r:*"))
        members = archive.infolist() if is_zip else archive.getmembers()
        require(len(members) <= 200000, "Too many archive members")
        for item in members:
            name = clean_relative(item.filename if is_zip else item.name)
            if not name:
                continue
            require(name not in seen, "Duplicate archive member: " + name)
            seen.add(name)
            mode = item.external_attr >> 16 if is_zip else item.mode
            if is_zip:
                kind = "dir" if item.is_dir() else "link" if stat.S_ISLNK(mode) else "file"
                require(stat.S_IFMT(mode) in (0, stat.S_IFDIR, stat.S_IFREG, stat.S_IFLNK), "Special ZIP member")
                size = item.file_size
            else:
                require(not item.sparse and (item.isfile() or item.isdir() or item.issym()), "Special/hardlink/sparse tar member")
                kind = "dir" if item.isdir() else "link" if item.issym() else "file"
                size = item.size
            require(0 <= size <= 512 * MIB, "Oversized/negative archive member")
            records.append([name, kind, mode, size, item])
        roots = {r[0].split("/")[0] for r in records}
        require(flat or len(roots) == 1, "Expected a single source archive root")
        mapped = []
        allocation = 0
        for name, kind, mode, size, item in records:
            rel = name if flat else "/".join(name.split("/")[1:])
            if not rel:
                require(kind == "dir", "Archive root is not a directory")
                continue
            if any(rel == prefix or rel.startswith(prefix + "/") for prefix in skip):
                continue
            target = None
            if kind == "link":
                target = archive.read(item).decode() if is_zip else item.linkname
                safe_link(rel, target)
            mapped.append((rel, kind, mode, size, item, target))
            allocation += 4096 if kind != "file" else ((size + 4095) // 4096) * 4096
        require(allocation <= 2 * GIB, "Source extraction exceeds per-archive bound")
        budget.check(allocation + 8 * MIB)
        destination.mkdir(parents=True)
        for rel, kind, mode, size, item, target in mapped:
            path = destination / rel
            require(contained(path.parent, destination), "Archive parent escapes source")
            require(not path.exists() and not path.is_symlink() or kind == "dir" and path.is_dir() and not path.is_symlink(),
                    "Archive path collides with another member")
            path.parent.mkdir(parents=True, exist_ok=True)
            if kind == "dir":
                path.mkdir(exist_ok=True)
            elif kind == "link":
                # Links are materialized last, so no extraction follows them.
                continue
            else:
                budget.check(size + 4096)
                source = archive.open(item) if is_zip else archive.extractfile(item)
                require(source is not None, "Missing archive payload")
                with source, path.open("xb") as output:
                    copy_stream(source, output, budget, size, maximum=512 * MIB)
                path.chmod(0o755 if mode & 0o111 else 0o644)
        for rel, kind, mode, size, item, target in mapped:
            if kind == "link":
                path = destination / rel
                require(not path.exists() and not path.is_symlink(), "Link collision")
                require(contained(path.parent, destination), "Link parent escapes source")
                os.symlink(target, path)
                require(contained(path, destination), "Link chain escapes source")
    return {"archive": archive_path.name, "members": len(mapped), "declaredAllocatedUpperEstimate": allocation,
            "omittedPrefixes": list(skip)}


class HttpsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        require(parsed.scheme == "https" and not parsed.username and not parsed.password, "Unsafe download redirect")
        require(parsed.hostname in {"github.com", "codeload.github.com", "release-assets.githubusercontent.com",
                                    "objects.githubusercontent.com", "github-releases.githubusercontent.com"}, "Unapproved redirect host")
        return super().redirect_request(request, response, code, message, headers, newurl)


def obtain(entry, destination, budget, *, download=False, local=None):
    expected = {k: entry.get(k) for k in ("size", "sha256", "sha1")}
    if destination.exists():
        return verify_file(destination, **expected)
    require(not destination.is_symlink(), "Archive destination is a symlink")
    require(local is not None or download, "Missing " + destination.name + "; provide --archive-dir/--dawn-supplement or --download")
    budget.check((entry.get("size") or 32 * MIB) + 4096)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".partial")
    require(not temporary.exists() and not temporary.is_symlink(), "Preserving incomplete download: " + str(temporary))
    if local is not None:
        verify_file(local, **expected)
        with local.open("rb") as source, temporary.open("xb") as target:
            copy_stream(source, target, budget, entry.get("size"))
    else:
        parsed = urllib.parse.urlsplit(entry["url"])
        require(parsed.scheme == "https" and parsed.hostname in {"github.com", "codeload.github.com"}, "Unapproved archive URL")
        request = urllib.request.Request(entry["url"], headers={"Accept-Encoding": "identity", "User-Agent": "LanType-native-build/1"})
        opener = urllib.request.build_opener(HttpsRedirect())
        with opener.open(request, timeout=60) as source, temporary.open("xb") as target:
            require(source.status == 200, "Source server did not return HTTP 200")
            declared = source.headers.get("Content-Length")
            if declared and entry.get("size") is not None:
                require(declared.isdigit() and int(declared) == entry["size"], "Download Content-Length differs from source lock")
            copy_stream(source, target, budget, entry.get("size"), maximum=entry.get("maximum", 384 * MIB))
    result = verify_file(temporary, **expected)
    temporary.rename(destination)
    return result


def tree_manifest(roots, work):
    records = []
    for root in roots:
        require(root.is_dir() and contained(root, work), "Missing/escaped source tree: " + str(root))
        for base, dirs, files in os.walk(root, followlinks=False):
            dirs.sort()
            for name in sorted(files + [n for n in dirs if (Path(base) / n).is_symlink()]):
                path = Path(base) / name
                relative = str(path.relative_to(work))
                info = path.lstat()
                if path.is_symlink():
                    require(contained(path, root), "Source link escaped its tree")
                    records.append({"path": relative, "link": os.readlink(path)})
                else:
                    require(stat.S_ISREG(info.st_mode), "Nonregular source input")
                    records.append({"path": relative, "bytes": info.st_size,
                                    "executable": bool(info.st_mode & 0o111), "sha256": file_hash(path)})
            dirs[:] = [n for n in dirs if not (Path(base) / n).is_symlink()]
    return sorted(records, key=lambda x: x["path"])


def cmake_cache(path):
    result = {}
    for line in path.read_text().splitlines():
        match = re.match(r"([^#/:][^:]*):[^=]+=(.*)$", line)
        if match:
            result[match[1]] = match[2]
    return result


class Builder:
    def __init__(self, args):
        self.args = args
        self.work = args.work_root.absolute()
        self.budget = Budget(self.work)
        self.state_path = self.work / "receipts/state.json"
        self.ort = self.work / "src/runtime-onnxruntime"
        self.dawn = self.work / "src/ort-dawn"
        self.cpuinfo = self.work / "src/onnx-dependency-pytorch_cpuinfo"
        self.build = self.work / "build/Release"
        self.sdk, self.ndk, self.cmake = args.sdk.resolve(), args.ndk.resolve(), args.cmake.resolve()
        self.lock_handle = None
        self.process = None
        self.base, self.plan, self.webgpu, self.publication = [read_json(ROOT / p) for p in LOCK_FILES]
        self.validate_locks()
        self.entries = {entry["id"]: entry for entry in self.base["sources"]}
        source = self.entries["runtime-onnxruntime"]
        require(source["commit"] == ORT_COMMIT and source["version"] == "1.28.0", "Unexpected ORT source")
        self.fingerprint = hashlib.sha256(json_bytes({
            "scriptSha256": file_hash(Path(__file__)),
            "locks": {p: file_hash(ROOT / p) for p in LOCK_FILES},
            "patch": CPUINFO_PATCH_SHA, "ndkVersion": NDK_VERSION, "cmakeVersion": CMAKE_VERSION,
            "sdk": str(self.sdk), "ndk": str(self.ndk), "cmake": str(self.cmake),
            "work": str(self.work), "jobs": args.jobs, "abi": "arm64-v8a", "api": 28,
            "lto": True, "providers": ["CPU", "NNAPI", "XNNPACK", "WebGPU"]})).hexdigest()
        known = {"lost+found", ".lantype-ort-owner.json", ".lantype-ort.lock", "archives", "src", "mirror", "tools",
                 "build", "tmp", "cache", "receipts", "logs", "candidate", "config"}
        owner = self.work / ".lantype-ort-owner.json"
        if owner.exists():
            require(read_json(owner).get("fingerprint") == self.fingerprint, "Work root belongs to different inputs/tools; preserve it and use a new mount")
            require(not ({p.name for p in self.work.iterdir()} - known), "Unknown files at work-root top level; preserving them")
        else:
            require({p.name for p in self.work.iterdir()} <= {"lost+found"}, "Refusing to adopt nonempty work filesystem")
            write_json(owner, {"schemaVersion": 1, "fingerprint": self.fingerprint, "createdUtc": now()})
        self.lock_handle = (self.work / ".lantype-ort.lock").open("a+")
        try:
            fcntl.flock(self.lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise BuildError("Another native build owns this work root") from error
        for directory in ("archives", "src", "mirror", "tools", "build", "tmp", "cache", "receipts", "logs", "config"):
            path = self.work / directory
            require(not path.is_symlink(), "Work directory cannot be a symlink")
            path.mkdir(exist_ok=True)
        self.state = read_json(self.state_path) if self.state_path.exists() else {
            "schemaVersion": 1, "fingerprint": self.fingerprint, "createdUtc": now(),
            "sources": {}, "patches": [], "stages": {}, "archives": {}}
        require(self.state["fingerprint"] == self.fingerprint, "State/input fingerprint changed")
        self.env = os.environ.copy()
        for key in ("CC", "CXX", "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS", "CMAKE_PREFIX_PATH", "CMAKE_TOOLCHAIN_FILE"):
            self.env.pop(key, None)
        self.env.update({"TMPDIR": str(self.work / "tmp"), "TMP": str(self.work / "tmp"), "TEMP": str(self.work / "tmp"),
                         "XDG_CACHE_HOME": str(self.work / "cache"), "PIP_CACHE_DIR": str(self.work / "cache/pip"),
                         "CCACHE_DIR": str(self.work / "cache/ccache"), "CCACHE_DISABLE": "1",
                         "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "PIP_NO_INPUT": "1",
                         "ANDROID_HOME": str(self.sdk), "ANDROID_SDK_ROOT": str(self.sdk), "ANDROID_NDK_HOME": str(self.ndk),
                         "CMAKE_BUILD_PARALLEL_LEVEL": str(args.jobs), "LC_ALL": "C.UTF-8"})
        self.tools = self.check_tools()
        previous_tools = self.state.get("tools")
        require(previous_tools is None or previous_tools == self.tools, "Preinstalled tool identity changed since previous stage")
        self.state["tools"] = self.tools
        self.save()

    def validate_locks(self):
        loader = importlib.util.spec_from_file_location("lantype_dawn_collector", ROOT / "scripts/collect-dawn-source-supplement.py")
        module = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(module)
        module.validate_plan(self.plan, self.base)
        require(self.webgpu["planSha256"] == file_hash(ROOT / LOCK_FILES[1]), "Dawn plan hash changed")
        # The collection receipt predates later source-lock metadata additions.
        # validate_plan checks reused archive identities; prepare separately
        # matches every active dependency to this fixed ORT's deps.txt.
        require(re.fullmatch(r"[0-9a-f]{64}", self.webgpu["baseLockSha256"]), "Invalid historical base-lock identity")
        require(self.publication["status"] == "reviewed-and-published-verified", "Dawn publication is not reviewed")
        require(self.publication["rawCollectionLock"]["sha256"] == file_hash(ROOT / LOCK_FILES[2]), "Published Dawn lock hash changed")
        release = self.publication["release"]
        require(release["sha256"] == SUPPLEMENT_SHA and release["bytes"] == SUPPLEMENT_BYTES
                and release["assetUrl"] == "https://github.com/ZPJJJ/LanType/releases/download/v1.1.1-rc1/" + SUPPLEMENT_NAME + ".zip",
                "Unexpected Dawn supplement release")
        require(self.webgpu["ortPatches"] == self.plan["ortPatches"], "Dawn patch plan mismatch")
        planned = {s["id"]: s for s in self.plan["sources"]}
        require(len(self.webgpu["sources"]) == 7, "Expected seven Dawn sources")
        for entry in self.webgpu["sources"]:
            require(entry["id"] in planned, "Unexpected Dawn source")
            for key in ("commit", "archiveUrl", "archiveFilename", "installPath", "archiveLayout"):
                require(entry[key] == planned[entry["id"]][key], "Dawn source differs from plan: " + key)
            require(re.fullmatch(r"[0-9a-f]{64}", entry["archiveSha256"]) and 0 < entry["archiveBytes"] < 128 * MIB, "Invalid Dawn archive identity")
        verify_file(ROOT / CPUINFO_PATCH, sha256=CPUINFO_PATCH_SHA)

    def save(self):
        self.state["updatedUtc"] = now()
        self.state["budget"] = self.budget.receipt()
        self.state["baseLockIdentity"] = {
            "historicalCollectionSha256": self.webgpu["baseLockSha256"],
            "currentSha256": file_hash(ROOT / LOCK_FILES[0]),
            "correspondence": "reused archive identities plus fixed-ORT deps.txt URL/SHA1 and current archive SHA256"}
        write_json(self.state_path, self.state)

    def check_tools(self):
        require(platform.machine() == "x86_64", "This pinned protoc/toolchain recipe targets a Linux x86_64 host")
        require(self.sdk.is_dir() and self.ndk.is_dir() and not contained(self.ndk, self.work), "Expected preinstalled read-only SDK/NDK")
        props = (self.ndk / "source.properties").read_text()
        require(re.search(r"^Pkg.Revision\s*=\s*" + re.escape(NDK_VERSION) + r"\s*$", props, re.M), "Expected preinstalled NDK " + NDK_VERSION)
        require(self.cmake.is_file() and not contained(self.cmake, self.work), "Expected preinstalled CMake")
        cmake_version = self.command([str(self.cmake), "--version"], "cmake-version", timeout=30).splitlines()[0]
        require(cmake_version == "cmake version " + CMAKE_VERSION, "Expected CMake " + CMAKE_VERSION)
        self.ninja = Path(shutil.which("ninja") or "missing-ninja").resolve()
        require(self.ninja.is_file(), "Preinstalled Ninja missing")
        self.patch = Path(shutil.which("patch") or "missing-patch").resolve()
        require(self.patch.is_file(), "GNU patch is required")
        toolchain = self.ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin"
        self.readelf = toolchain / "llvm-readelf"
        return {"ndkVersion": NDK_VERSION, "cmakeVersion": CMAKE_VERSION,
                "officialOrtCiNdkVersion": "28.0.13004108",
                "selectionReason": "LanType selects the preinstalled NDK 29 to avoid a second heavy toolchain download; not vendor reproduction",
                "cmakeSha256": file_hash(self.cmake), "ndkPropertiesSha256": file_hash(self.ndk / "source.properties"),
                "clangSha256": file_hash(toolchain / "clang"), "linkerSha256": file_hash(toolchain / "ld.lld"),
                "ninjaVersion": self.command([str(self.ninja), "--version"], "ninja-version", timeout=30).strip(),
                "ninjaSha256": file_hash(self.ninja), "pythonVersion": platform.python_version()}

    def stop_process(self):
        if self.process is None:
            return
        with contextlib.suppress(ProcessLookupError):
            os.killpg(self.process.pid, signal.SIGTERM)
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=10)
        self.process = None

    def command(self, command, label, *, cwd=None, timeout=4 * 3600, allow_failure=False):
        self.budget.check()
        label = re.sub(r"[^A-Za-z0-9_.-]", "_", label)
        log_path = self.work / "logs" / (label + "-" + str(time.time_ns()) + ".log")
        record = {"command": command, "cwd": str(cwd or self.work), "startedUtc": now(), "log": str(log_path.relative_to(self.work))}
        started = time.monotonic()
        recorded = False
        print("RUN", shlex.join(command), flush=True)
        try:
            with log_path.open("xb") as log:
                self.process = subprocess.Popen(command, cwd=cwd or self.work, env=self.env,
                                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                                start_new_session=True)
                while self.process.poll() is None:
                    self.budget.check()
                    require(log_path.stat().st_size < MAX_LOG_BYTES, "Command log exceeded 64 MiB; stopping")
                    require(time.monotonic() - started < timeout, "Command time limit exceeded")
                    time.sleep(0.25)
                code = self.process.returncode
                self.process = None
            record["exitCode"] = code
            record["elapsedSeconds"] = round(time.monotonic() - started, 3)
            self.state.setdefault("commands", []).append(record)
            recorded = True
            self.save()
            require(log_path.stat().st_size < MAX_LOG_BYTES, "Command log exceeded 64 MiB")
            result = log_path.read_text(errors="replace")
            if code != 0 and not allow_failure:
                raise BuildError("Command failed (" + str(code) + "), see " + str(log_path) + "\n" + result[-6000:])
            return result if not allow_failure else (code, result)
        except BaseException:
            self.stop_process()
            record["stoppedUtc"] = now()
            if not recorded:
                self.state.setdefault("commands", []).append(record)
            self.save()
            raise

    def base_archive(self, identity):
        item = self.entries[identity]
        path = self.work / "archives" / item["archive_file"]
        local = self.args.archive_dir / item["archive_file"] if self.args.archive_dir else None
        if local is not None and not local.is_file():
            local = None
        result = obtain({"url": item["archive_url"], "size": item["archive_bytes"], "sha256": item["archive_sha256"],
                         "sha1": item.get("archive_sha1")}, path, self.budget, download=self.args.download, local=local)
        self.state["archives"][identity] = {"path": str(path.relative_to(self.work)), **result}
        self.save()
        return path

    def extract_source(self, identity, archive, destination, *, flat=False, skip=()):
        if identity in self.state["sources"]:
            require(self.state["sources"][identity]["path"] == str(destination.relative_to(self.work)) and destination.is_dir(), "Source checkpoint mismatch")
            return
        report = safe_extract(archive, destination, self.budget, flat=flat, skip=skip)
        self.state["sources"][identity] = {"path": str(destination.relative_to(self.work)), **report}
        self.save()

    def apply_patch(self, path, destination, identity, expected_sha):
        verify_file(path, sha256=expected_sha)
        if any(item["id"] == identity for item in self.state["patches"]):
            return
        dawn_target = DAWN_PATCH_TARGETS.get(identity)
        fuzz_limit = 2 if dawn_target else 0
        target_evidence = None
        if dawn_target:
            target, before, after = dawn_target
            observed = verify_file(destination / target)["sha256"]
            require(observed in (before, after), "Dawn patch target identity changed: " + identity)
            target_evidence = {"path": target, "expectedBeforeSha256": before,
                               "observedBeforeSha256": observed, "expectedAfterSha256": after}
        args = [str(self.patch), "--batch", "--binary", "--ignore-whitespace", "--fuzz=" + str(fuzz_limit),
                "--no-backup-if-mismatch", "-p1", "-i", str(path)]
        status, _ = self.command(args + ["--forward", "--dry-run"], identity + "-check", cwd=destination, timeout=60, allow_failure=True)
        if status == 0:
            self.command(args + ["--forward"], identity, cwd=destination, timeout=60)
            mode = "applied"
        else:
            status, _ = self.command(args + ["--reverse", "--dry-run"], identity + "-already-applied", cwd=destination, timeout=60, allow_failure=True)
            require(status == 0, "Patch does not apply cleanly in either direction: " + identity)
            mode = "recovered-after-interruption"
        if dawn_target:
            verify_file(destination / dawn_target[0], sha256=dawn_target[2])
        self.state["patches"].append({"id": identity, "sha256": expected_sha, "path": str(path), "mode": mode,
                                      "maximumContextFuzz": fuzz_limit, "targetIdentity": target_evidence})
        self.save()

    def prepare(self):
        if self.state["stages"].get("prepare") == "passed":
            self.verify_archives()
            self.verify_manifest("prepared-sources.json", [self.work / "src", self.work / "tools/protoc"])
            return {"resumed": True}
        archive = self.base_archive("runtime-onnxruntime")
        self.extract_source("runtime-onnxruntime", archive, self.ort)
        require((self.ort / "VERSION_NUMBER").read_text().strip() == "1.28.0", "Unexpected ORT version")
        deps = {}
        for line in (self.ort / "cmake/deps.txt").read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                name, url, sha1 = line.split(";")
                deps[name] = (url, sha1)
        for name in DEPS:
            identity = "onnx-dependency-" + name
            item = self.entries[identity]
            require(deps[name] == (item["archive_url"], item["archive_sha1"]), "ORT deps.txt and source lock disagree: " + name)
            archive = self.base_archive(identity)
            mirror_relative = item["archive_url"].removeprefix("https://")
            clean_relative(mirror_relative)
            mirror = self.work / "mirror" / mirror_relative
            mirror.parent.mkdir(parents=True, exist_ok=True)
            if mirror.exists():
                verify_file(mirror, sha256=item["archive_sha256"])
            else:
                require(not mirror.is_symlink(), "Symlink mirror destination")
                os.link(archive, mirror)
            if name == "pytorch_cpuinfo":
                require(CPUINFO_COMMIT in item["archive_url"], "Wrong cpuinfo revision")
                self.extract_source(identity, archive, self.cpuinfo)
        cpu_source = self.cpuinfo / "src/arm/linux/init.c"
        require(file_hash(cpu_source) in (CPUINFO_BEFORE, CPUINFO_AFTER), "Unexpected cpuinfo production source")
        self.apply_patch(ROOT / CPUINFO_PATCH, self.cpuinfo, "cpuinfo-production", CPUINFO_PATCH_SHA)
        verify_file(cpu_source, sha256=CPUINFO_AFTER)
        self.prepare_dawn()
        protoc_url, protoc_sha1 = deps["protoc_linux_x64"]
        require(protoc_sha1 == "338462004aa5be9fba45b35b5b4be43f69b47a90", "Unexpected protoc pin")
        protoc_archive = self.work / "archives/protoc-21.12-linux-x86_64.zip"
        tool = obtain({"url": protoc_url, "sha1": protoc_sha1, "maximum": 32 * MIB}, protoc_archive, self.budget, download=self.args.download)
        self.extract_source("protoc-21.12-linux-x86_64", protoc_archive, self.work / "tools/protoc", flat=True)
        protoc = self.work / "tools/protoc/bin/protoc"
        require(self.command([str(protoc), "--version"], "protoc-version", timeout=30).strip() == "libprotoc 3.21.12", "Unexpected protoc version")
        self.state["protoc"] = {**tool, "upstreamPinMethod": "SHA-1 in fixed ORT deps.txt", "executableSha256": file_hash(protoc)}
        self.snapshot_manifest("prepared-sources.json", [self.work / "src", self.work / "tools/protoc"])
        return {"sourceCount": len(self.state["sources"]), "archiveCount": len(self.state["archives"]),
                "cpuinfoPatchedSourceSha256": file_hash(cpu_source), "protoc": self.state["protoc"]}

    def prepare_dawn(self):
        release = self.publication["release"]
        destination = self.work / "archives" / release["file"]
        missing = [s for s in self.webgpu["sources"] if not (self.work / "archives" / s["archiveFilename"]).exists()]
        if missing:
            obtain({"url": release["assetUrl"], "size": SUPPLEMENT_BYTES, "sha256": SUPPLEMENT_SHA}, destination,
                   self.budget, download=self.args.download, local=self.args.dawn_supplement)
            with zipfile.ZipFile(destination) as package:
                for source in missing:
                    member = SUPPLEMENT_NAME + "/archives/" + source["archiveFilename"]
                    matches = [item for item in package.infolist() if item.filename == member]
                    require(len(matches) == 1 and matches[0].file_size == source["archiveBytes"], "Dawn supplement member mismatch")
                    target = self.work / "archives" / source["archiveFilename"]
                    with package.open(matches[0]) as stream, target.open("xb") as output:
                        copy_stream(stream, output, self.budget, source["archiveBytes"])
                    verify_file(target, size=source["archiveBytes"], sha256=source["archiveSha256"])
            # This exact, verified container is a redundant copy of the seven
            # archives now retained individually. No unknown file is removed.
            verify_file(destination, size=SUPPLEMENT_BYTES, sha256=SUPPLEMENT_SHA)
            destination.unlink()
            self.state["supplement"] = {"sha256": SUPPLEMENT_SHA, "bytes": SUPPLEMENT_BYTES, "containerRemovedAfterVerifiedExtraction": True}
            self.save()
        for source in sorted(self.webgpu["sources"], key=lambda s: len(PurePosixPath(s["installPath"]).parts)):
            archive = self.work / "archives" / source["archiveFilename"]
            result = verify_file(archive, size=source["archiveBytes"], sha256=source["archiveSha256"], sha1=source.get("expectedArchiveSha1"))
            self.state["archives"][source["id"]] = {"path": str(archive.relative_to(self.work)), **result}
            prefix = "vendor/native-sources/runtime-onnxruntime-dawn"
            relative = source["installPath"].removeprefix(prefix).lstrip("/")
            target = self.dawn / relative
            # Git archives may contain empty submodule placeholder directories.
            if target.exists() and target != self.dawn and source["id"] not in self.state["sources"]:
                require(target.is_dir() and not target.is_symlink() and not any(target.iterdir()), "Preserving nonempty Dawn dependency location")
                target.rmdir()
            self.extract_source(source["id"], archive, target, flat=source["archiveLayout"] == "flat",
                                skip=("test",) if source["id"] == "ort-dawn" else ())
        for patch in sorted(self.webgpu["ortPatches"], key=lambda p: p["applyOrder"]):
            self.apply_patch(self.ort / patch["path"], self.dawn, "dawn-" + str(patch["applyOrder"]), patch["sha256"])

    def snapshot_manifest(self, filename, roots):
        result = tree_manifest(roots, self.work)
        write_json(self.work / "receipts" / filename, result)
        self.state.setdefault("manifests", {})[filename] = {"sha256": file_hash(self.work / "receipts" / filename),
                                                          "files": len(result), "roots": [str(p.relative_to(self.work)) for p in roots]}
        self.save()

    def verify_manifest(self, filename, roots):
        path = self.work / "receipts" / filename
        verify_file(path, sha256=self.state["manifests"][filename]["sha256"])
        expected = read_json(path)
        require(tree_manifest(roots, self.work) == expected, "Source files changed since checkpoint: " + filename)

    def arguments(self):
        defines = {
            "onnxruntime_BUILD_UNIT_TESTS": "OFF", "onnxruntime_BUILD_JAVA": "OFF",
            "onnxruntime_USE_EP_API_ADAPTERS": "OFF", "onnxruntime_BUILD_DAWN_SHARED_LIBRARY": "OFF",
            "onnxruntime_CUSTOM_DAWN_SRC_PATH": str(self.dawn),
            "FETCHCONTENT_SOURCE_DIR_PYTORCH_CPUINFO": str(self.cpuinfo),
            "FETCHCONTENT_TRY_FIND_PACKAGE_MODE": "NEVER", "FETCHCONTENT_UPDATES_DISCONNECTED": "ON",
            "CMAKE_MAKE_PROGRAM": str(self.ninja), "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
            "ANDROID_STL": "c++_static",
            "CMAKE_CXX_STANDARD": "20", "CMAKE_JOB_POOLS": "compile_pool=2;link_pool=1",
            "CMAKE_JOB_POOL_COMPILE": "compile_pool", "CMAKE_JOB_POOL_LINK": "link_pool",
            "CMAKE_INSTALL_PREFIX": str(self.work / "build/install"),
            "Python_EXECUTABLE": sys.executable, "Python3_EXECUTABLE": sys.executable,
        }
        return [sys.executable, str(self.ort / "tools/ci_build/build.py"),
                "--build_dir", str(self.work / "build"), "--config", "Release", "--android",
                "--android_abi", "arm64-v8a", "--android_api", "28", "--android_sdk_path", str(self.sdk),
                "--android_ndk_path", str(self.ndk), "--cmake_path", str(self.cmake), "--cmake_generator", "Ninja",
                "--build_shared_lib", "--use_nnapi", "--use_xnnpack", "--use_webgpu", "static_lib", "--enable_lto",
                "--skip_tests", "--skip_submodule_sync", "--parallel", str(self.args.jobs),
                "--path_to_protoc_exe", str(self.work / "tools/protoc/bin/protoc"),
                "--cmake_deps_mirror_dir", str(self.work / "mirror"),
                "--cmake_extra_defines", *[key + "=" + value for key, value in defines.items()]]

    def configured_roots(self):
        roots = [self.work / "src", self.work / "tools/protoc"]
        for key, project in DEPS.items():
            if key != "pytorch_cpuinfo":
                roots.append(self.build / "_deps" / (project + "-src"))
        return roots

    def verify_archives(self):
        for identity, record in self.state["archives"].items():
            verify_file(self.work / record["path"], size=record["bytes"], sha256=record["sha256"], sha1=record.get("sha1"))
        for name in DEPS:
            entry = self.entries["onnx-dependency-" + name]
            mirror = self.work / "mirror" / entry["archive_url"].removeprefix("https://")
            verify_file(mirror, size=entry["archive_bytes"], sha256=entry["archive_sha256"])
        if "protoc" in self.state:
            verify_file(self.work / "tools/protoc/bin/protoc", sha256=self.state["protoc"]["executableSha256"])

    def configuration_evidence(self):
        cache = cmake_cache(self.build / "CMakeCache.txt")
        expected = {
            "CMAKE_BUILD_TYPE": "Release", "ANDROID_ABI": "arm64-v8a", "ANDROID_PLATFORM": "android-28",
            "ANDROID_STL": "c++_static",
            "CMAKE_CXX_STANDARD": "20", "onnxruntime_BUILD_SHARED_LIB": "ON", "onnxruntime_ENABLE_LTO": "ON",
            "onnxruntime_USE_NNAPI_BUILTIN": "ON", "onnxruntime_USE_XNNPACK": "ON", "onnxruntime_USE_WEBGPU": "ON",
            "onnxruntime_MINIMAL_BUILD": "OFF", "onnxruntime_DISABLE_CONTRIB_OPS": "OFF",
            "onnxruntime_DISABLE_ML_OPS": "OFF", "onnxruntime_BUILD_UNIT_TESTS": "OFF", "onnxruntime_BUILD_JAVA": "OFF",
            "onnxruntime_USE_VCPKG": "OFF", "onnxruntime_USE_EP_API_ADAPTERS": "OFF",
            "onnxruntime_BUILD_DAWN_SHARED_LIBRARY": "OFF", "DAWN_FETCH_DEPENDENCIES": "OFF",
            "DAWN_ENABLE_VULKAN": "ON", "TINT_BUILD_SPV_WRITER": "ON", "TINT_BUILD_WGSL_WRITER": "ON",
            "DAWN_BUILD_TESTS": "OFF", "DAWN_BUILD_SAMPLES": "OFF", "TINT_BUILD_TESTS": "OFF",
            "CPUINFO_BUILD_UNIT_TESTS": "OFF", "CPUINFO_BUILD_MOCK_TESTS": "OFF",
            "XNNPACK_BUILD_TESTS": "OFF", "XNNPACK_BUILD_BENCHMARKS": "OFF",
        }
        for key, value in expected.items():
            require(cache.get(key) == value, "Configuration gate failed: " + key + "=" + str(cache.get(key)) + ", expected " + value)
        require(Path(cache["FETCHCONTENT_SOURCE_DIR_PYTORCH_CPUINFO"]).resolve() == self.cpuinfo, "cpuinfo override was not selected")
        require(Path(cache["onnxruntime_CUSTOM_DAWN_SRC_PATH"]).resolve() == self.dawn, "Dawn override was not selected")
        verify_file(self.cpuinfo / "src/arm/linux/init.c", sha256=CPUINFO_AFTER)
        commands_path = self.build / "compile_commands.json"
        require(commands_path.stat().st_size < 64 * MIB, "Compile commands unexpectedly large")
        commands = json.loads(commands_path.read_text())
        markers = {"cpu": "/onnxruntime/core/providers/cpu/", "nnapi": "/onnxruntime/core/providers/nnapi/",
                   "xnnpack": "/onnxruntime/core/providers/xnnpack/", "webgpu": "/onnxruntime/core/providers/webgpu/",
                   "dawn": "/src/dawn/native/", "tint": "/src/tint/", "cpuinfo": "/src/arm/linux/init.c"}
        selected = {key: [] for key in markers}
        for item in commands:
            source = Path(item["file"])
            if not source.is_absolute():
                source = Path(item["directory"]) / source
            require(contained(source, self.work) or contained(source, self.ndk), "Compile source is outside controlled inputs: " + str(source))
            for key, marker in markers.items():
                if marker in source.as_posix():
                    selected[key].append(item)
        for key, items in selected.items():
            require(items, "Missing implementation compile entries: " + key)
        require(any(Path(item["file"]).resolve() == self.cpuinfo / "src/arm/linux/init.c" for item in selected["cpuinfo"]),
                "Patched cpuinfo file is absent from actual compiler input plan")
        write_json(self.work / "receipts/provider-compile-inputs.json", selected)
        files = ("CMakeCache.txt", "compile_commands.json", "build.ninja", "CMakeFiles/rules.ninja")
        return {"cacheGates": expected, "implementationCompileEntryCounts": {key: len(items) for key, items in selected.items()},
                "generatedBuildFiles": {name: {"sha256": file_hash(self.build / name), "bytes": (self.build / name).stat().st_size} for name in files},
                "cpuinfoCompiledPath": str(self.cpuinfo / "src/arm/linux/init.c"), "cpuinfoPatchedSha256": CPUINFO_AFTER,
                "scope": "compile commands prove selected inputs, not runtime provider availability or device acceptance"}

    def configure(self):
        require(self.state["stages"].get("prepare") == "passed", "Run successful --stage prepare first")
        self.verify_archives()
        self.verify_manifest("prepared-sources.json", [self.work / "src", self.work / "tools/protoc"])
        if self.state["stages"].get("configure") == "passed":
            self.verify_manifest("configured-sources.json", self.configured_roots())
            return self.configuration_evidence()
        self.command(self.arguments() + ["--update"], "configure", cwd=self.ort, timeout=1800)
        evidence = self.configuration_evidence()
        self.snapshot_manifest("configured-sources.json", self.configured_roots())
        return evidence

    def build_library(self):
        require(self.state["stages"].get("configure") == "passed", "Run successful --stage configure first")
        self.verify_manifest("configured-sources.json", self.configured_roots())
        evidence = self.configuration_evidence()
        self.command(self.arguments() + ["--build", "--targets", "onnxruntime"], "build-onnxruntime", cwd=self.ort)
        self.verify_manifest("configured-sources.json", self.configured_roots())
        library = self.build / "libonnxruntime.so"
        require(library.is_file() and contained(library, self.build), "Expected ORT library was not produced")
        ninja_log = self.build / ".ninja_log"
        return {"output": {"path": str(library.relative_to(self.work)), **verify_file(library)},
                "configuration": evidence, "ninjaLogSha256": file_hash(ninja_log),
                "runtimeExecuted": False, "testsBuiltOrRun": False}

    def verify(self):
        require(self.state["stages"].get("build") == "passed", "Run successful --stage build first")
        self.verify_manifest("configured-sources.json", self.configured_roots())
        evidence = self.configuration_evidence()
        library = self.build / "libonnxruntime.so"
        previous = read_json(self.work / "receipts/build.json")["result"]["output"]
        identity = verify_file(library, size=previous["bytes"], sha256=previous["sha256"])
        headers = self.command([str(self.readelf), "--file-header", "--program-headers", "--dynamic", "--version-info", "--dyn-syms", "--wide", str(library)], "elf-inspection", timeout=60)
        require("AArch64" in headers and "VERS_1.28.0" in headers, "Expected AArch64/versioned ABI missing")
        for symbol in ("OrtGetApiBase", "OrtSessionOptionsAppendExecutionProvider_CPU", "OrtSessionOptionsAppendExecutionProvider_Nnapi"):
            require(re.search(re.escape(symbol) + r"@@?VERS_1\.28\.0\b", headers), "Missing versioned export: " + symbol)
        return {"output": {"path": str(library.relative_to(self.work)), **identity}, "configuration": evidence,
                "basicElfGate": "passed", "completeConsumerAbiGate": "run scripts/verify-ort-abi.py separately",
                "runtimeAcceptance": "not run; ordinary Android initialization and model tests remain required",
                "vendorBinaryIdenticalReproduction": False, "publishedOrInstalled": False}

    def run(self):
        functions = {"prepare": self.prepare, "configure": self.configure, "build": self.build_library, "verify": self.verify}
        stage = self.args.stage
        started = now()
        self.state["stages"][stage] = "running"
        # Preserve the preceding successful receipt for same-stage resumptions.
        prior = self.work / "receipts" / (stage + ".json")
        if prior.exists() and read_json(prior).get("status") == "passed":
            self.state["stages"][stage] = "passed"
        self.save()
        try:
            result = functions[stage]()
            self.budget.check()
            report = {"schemaVersion": 1, "stage": stage, "status": "passed", "startedUtc": started, "finishedUtc": now(),
                      "fingerprint": self.fingerprint, "tools": self.tools, "budget": self.budget.receipt(), "result": result}
            write_json(prior, report)
            self.state["stages"][stage] = "passed"
            self.save()
            print("ORT_NATIVE_STAGE_PASSED", stage, str(prior), flush=True)
        except BaseException as error:
            self.stop_process()
            self.state["stages"][stage] = "failed"
            write_json(self.work / "receipts/failure.json", {"stage": stage, "status": "failed", "timeUtc": now(),
                       "error": str(error), "budget": self.budget.receipt(), "previousSuccessfulReceiptsRetained": True})
            self.save()
            raise


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("prepare", "configure", "build", "verify"))
    parser.add_argument("--work-root", required=True, type=Path, help="Exclusive pre-mounted filesystem, capacity <=4608 MiB")
    parser.add_argument("--sdk", required=True, type=Path)
    parser.add_argument("--ndk", required=True, type=Path, help="Preinstalled 29.0.14206865; never downloaded here")
    parser.add_argument("--cmake", required=True, type=Path, help="Preinstalled CMake 3.31.6 executable")
    parser.add_argument("--archive-dir", type=Path, help="Optional existing archive directory, read only")
    parser.add_argument("--dawn-supplement", type=Path, help="Optional published source-supplement ZIP, read only")
    parser.add_argument("--download", action="store_true", help="Permit pinned downloads during prepare only")
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=2)
    args = parser.parse_args(argv)
    require(not args.download or args.stage == "prepare", "--download is only valid for prepare")
    require(" " not in str(ROOT) and " " not in str(args.work_root), "Repository/work paths must not contain spaces")
    return args


def main():
    args = parse_arguments()
    # Existing repository storage policy remains active; no bypass flag.
    import storage_guard
    storage_guard.check_storage(ROOT)
    builder = None
    try:
        builder = Builder(args)
        def interrupted(signum, frame):
            raise BuildError("Interrupted by signal " + str(signum))
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        builder.run()
    finally:
        if builder:
            builder.stop_process()
            if builder.lock_handle:
                builder.lock_handle.close()


if __name__ == "__main__":
    try:
        main()
    except (BuildError, OSError, ValueError, KeyError, zipfile.BadZipFile, tarfile.TarError) as error:
        print("ORT_NATIVE_BUILD_STOPPED:", str(error), file=sys.stderr)
        sys.exit(1)
