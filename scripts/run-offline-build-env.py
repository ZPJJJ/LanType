#!/usr/bin/env python3
"""Run the existing APK build inside its dedicated 4608 MiB work volume.

Only the allocation measurement is shared with native-build QA. This wrapper
does not build a native probe or reuse a QA acceptance result. The remaining
512 MiB is asserted at checkpoints, not enforced as a whole-job filesystem quota.
Installed JDK/SDK packages are inputs; all new source, SDK, Java/Gradle cache,
temporary and build files belong to this volume. The operating-system HOME is
unchanged, including for storage_guard.py's host free-space preflight.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager, ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import signal
import stat
import subprocess
import sys
import time

MIB = 1024**2
CAPACITY = 4608 * MIB
OUTSIDE_LIMIT = 512 * MIB
WORK_RESERVE = 256 * MIB
NDK = "29.0.14206865"
REPO = Path(__file__).resolve().parents[1]
MEASURE = runpy.run_path(str(REPO / "scripts/check-ort-build-overhead.py"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


@contextmanager
def owned_parent(root, path):
    """Open only real, current-user directories on this owned filesystem."""
    require(root.is_absolute() and root == root.resolve(strict=True), "Work root traverses a symlink")
    require(path.is_absolute() and path.is_relative_to(root) and path != root,
            "Owned path is outside the work root: " + str(path))
    relative = path.relative_to(root)
    require(all(part not in ("", ".", "..") for part in relative.parts), "Unsafe owned path")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(root, flags)
    device = os.fstat(descriptor).st_dev
    try:
        for part in relative.parts[:-1]:
            require(os.fstat(descriptor).st_uid == os.getuid(), "Owned parent has a different owner")
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            require(os.fstat(descriptor).st_dev == device, "Owned path crosses a filesystem")
        require(os.fstat(descriptor).st_uid == os.getuid(), "Owned parent has a different owner")
        yield descriptor, device
    finally:
        os.close(descriptor)


def read_owned(root, path, limit=4 * MIB):
    with owned_parent(root, path) as (parent, device):
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_dev == device and info.st_uid == os.getuid()
                    and info.st_size <= limit, "Invalid or oversized owned input: " + str(path))
            return stream.read(limit + 1)


def pinned_identity(value):
    require(isinstance(value, dict) and set(value) == {"bytes", "sha256"}, "Invalid archive identity")
    require(type(value["bytes"]) is int and 0 < value["bytes"] < CAPACITY
            and isinstance(value["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]),
            "Invalid archive size or SHA-256")
    return value


def filesystem_usage(path):
    info = os.statvfs(path)
    return {"capacityBytes": info.f_blocks * info.f_frsize,
            "usedBytes": (info.f_blocks - info.f_bfree) * info.f_frsize,
            "availableBytes": info.f_bavail * info.f_frsize}


def prune_runtime_archives(root, source, receipt_path):
    """Pure file operation; the CLI checks the independent bounded mount first.

    All receipts, pins and both cache entries are checked before either unlink.
    No caller-supplied path, glob, directory removal or output pruning is used.
    """
    require(source == root / "source", "Unexpected source directory")
    source_text = read_owned(root, source / "scripts/restore-base-runtime.py", MIB)
    assignments = [node.value for node in ast.parse(source_text).body
                   if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                       and target.id == "ARCHIVE" for target in node.targets)]
    require(len(assignments) == 1, "Expected one literal base ARCHIVE pin")
    base_pin = pinned_identity(ast.literal_eval(assignments[0]))
    lock_bytes = read_owned(root, source / "docs/licensing/ort-runtime.lock.json", MIB)
    lock = json.loads(lock_bytes)
    require(lock.get("kind") == "lantype-ort-runtime-lock" and lock.get("status") == "accepted"
            and lock.get("ortVersion") == "1.28.0" and lock.get("abi") == "arm64-v8a",
            "An accepted fixed ORT lock is required before cache pruning")
    ort_pin = pinned_identity(lock["distribution"]["archive"])
    reports = source / "app/build/reports/lantype-native"
    base_bytes = read_owned(root, reports / "base-restoration.json")
    ort_bytes = read_owned(root, reports / "ort-restoration.json")
    base, ort = json.loads(base_bytes), json.loads(ort_bytes)
    require(base.get("kind") == "lantype-base-runtime-receipt" and base.get("ok") is True
            and type(base.get("verifiedFiles")) is int and base["verifiedFiles"] > 0,
            "Base restoration did not succeed")
    require(ort.get("kind") == "lantype-ort-runtime-restore-receipt" and ort.get("ok") is True
            and ort.get("lockSha256") == hashlib.sha256(lock_bytes).hexdigest()
            and ort.get("outputs") == lock.get("outputs")
            and ort.get("boundedWorkRoot") == str(root)
            and ort.get("outputDirectory") == str(source / "vendor/ort-runtime")
            and ort.get("storageReserveBytes") == WORK_RESERVE, "ORT restoration did not succeed for this lock and volume")
    lock_names = ("resources.lock.json", "native-prebuilt.lock.json", "camerax-rebuilt.lock.json")
    actual_locks = {name: hashlib.sha256(read_owned(root, source / "docs/licensing" / name)).hexdigest()
                    for name in lock_names}
    require(base.get("lockSha256") == actual_locks, "Base source locks changed since restoration")
    for label, row, pin in (("base", base, base_pin), ("ort", ort, ort_pin)):
        require("archive" not in row or row["archive"] == pin, label + " restoration used another archive")
    require(base.get("archiveVerified") is not True or base.get("archive") == base_pin,
            "Base archive verification has no matching identity")
    require(ort.get("alreadyPresent") is True or ort.get("archive") == ort_pin,
            "ORT download restoration has no matching archive identity")
    entries = (("base", source / ".gradle/base-runtime-archives" / (base_pin["sha256"] + ".zip"), base_pin,
                base.get("downloadPerformed") is True),
               ("ort", source / ".gradle/ort-runtime-archives" / (ort_pin["sha256"] + ".zip"), ort_pin,
                ort.get("alreadyPresent") is not True))
    row = {"schemaVersion": 1, "kind": "lantype-runtime-cache-prune", "ok": False,
           "scope": "Only two fixed downloadable cache ZIP names; inputs, outputs and evidence are retained.",
           "baseScriptSha256": hashlib.sha256(source_text).hexdigest(),
           "acceptedLockSha256": hashlib.sha256(lock_bytes).hexdigest(),
           "restoreReceiptSha256": {"base": hashlib.sha256(base_bytes).hexdigest(),
                                    "ort": hashlib.sha256(ort_bytes).hexdigest()},
           "volumeBefore": filesystem_usage(root), "files": []}
    receipt_stream = None
    try:
        with ExitStack() as stack:
            opened = []
            for label, path, pin, required in entries:
                item = {"name": label, "path": str(path), **pin, "disposition": "pending"}
                row["files"].append(item)
                try:
                    parent, device = stack.enter_context(owned_parent(root, path))
                    descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                except FileNotFoundError:
                    require(not required, "A ZIP used by this restoration disappeared: " + str(path))
                    item["disposition"] = "already-absent"
                    continue
                stream = stack.enter_context(os.fdopen(descriptor, "rb"))
                info = os.fstat(stream.fileno())
                require(stat.S_ISREG(info.st_mode) and info.st_dev == device and info.st_uid == os.getuid()
                        and info.st_size == pin["bytes"], "Invalid cache file type, owner, device or size: " + str(path))
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
                require(digest == pin["sha256"], "Cache ZIP SHA-256 mismatch: " + str(path))
                item.update(allocatedBytes=info.st_blocks * 512, device=info.st_dev, inode=info.st_ino,
                            hardLinkCount=info.st_nlink)
                opened.append((parent, path, info, item))
            # Both entries have now passed. Recheck both names before any unlink;
            # retained descriptors also prevent a different parent being followed.
            for parent, path, info, _ in opened:
                current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                require((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns, current.st_ctime_ns)
                        == (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns),
                        "Validated cache entry changed before removal: " + str(path))
            receipt_stream = receipt_path.open("x", encoding="utf-8")
            for parent, path, _, item in opened:
                os.unlink(path.name, dir_fd=parent)
                item["disposition"] = "removed"
        # All handles are closed before measuring the actually reclaimed blocks.
        row["ok"] = True
    finally:
        if receipt_stream is not None:
            row["volumeAfter"] = filesystem_usage(root)
            row["removedFileBytes"] = sum(item["bytes"] for item in row["files"] if item["disposition"] == "removed")
            row["observedFreedFilesystemBytes"] = row["volumeBefore"]["usedBytes"] - row["volumeAfter"]["usedBytes"]
            with receipt_stream:
                json.dump(row, receipt_stream, indent=2, sort_keys=True)
                receipt_stream.write("\n")
    return row


def properties(path):
    require(path.is_file() and path.stat().st_size <= MIB, "Missing or oversized tool metadata: " + str(path))
    return {key.strip(): value.strip().strip('"') for key, value in
            (line.split("=", 1) for line in path.read_text().splitlines()
             if "=" in line and not line.lstrip().startswith("#"))}


def component(directory, executables, files, key="Pkg.Revision", expected=None, package_metadata=True):
    row = {"directory": str(directory), "resolvedDirectory": str(directory.resolve()), "errors": []}
    try:
        revision = properties(directory / "source.properties").get(key)
        require(revision and (expected is None or revision == expected), "Unexpected SDK revision: " + str(revision))
        # A complete installed package has metadata already. sdkmanager must
        # never synthesize package.xml through a link into a host package.
        for name in (*executables, *files, *(("package.xml",) if package_metadata else ())):
            path = directory / name
            require(path.is_file(), "Missing tool input: " + str(path))
            if name in executables:
                require(os.access(path, os.X_OK), "Tool is not executable: " + str(path))
        row.update(revision=revision, metadataSha256=hashlib.sha256((directory / "source.properties").read_bytes()).hexdigest())
    except (OSError, ValueError) as error:
        row["errors"].append(str(error))
    row["usable"] = not row["errors"]
    return row


def start_ticks(pid):
    # /proc field 22; the parenthesized command name can contain spaces.
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def stop_group(pid):
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


class Driver:
    def __init__(self):
        self.temporary = MEASURE["real_directory"](os.environ["RUNNER_TEMP"], "RUNNER_TEMP")
        self.root = Path(os.environ["LANTYPE_OFFLINE_WORK_ROOT"])
        self.volume = Path(os.environ["LANTYPE_OFFLINE_VOLUME"])
        self.receipts = Path(os.environ["LANTYPE_OFFLINE_RECEIPTS"])
        for path, name in ((self.root, "lantype-offline-work"), (self.volume, "lantype-offline-volume.img"),
                           (self.receipts, "lantype-offline-receipts")):
            require(path == self.temporary / name and not path.is_symlink(), "Unexpected owned path: " + str(path))
        MEASURE["real_directory"](str(self.receipts), "Receipts")
        require(REPO == Path(os.environ["GITHUB_WORKSPACE"]).resolve(), "Run this helper from the original Actions checkout")
        self.source, self.sdk, self.evidence = (self.root / name for name in ("source", "sdk", "evidence"))
        self.host_sdk = Path(os.environ["LANTYPE_OFFLINE_HOST_SDK"]).resolve(strict=True)
        self.jdk = Path(os.environ["JAVA_HOME"]).resolve(strict=True)
        self.active = self.receipts / "active-command.json"
        self.env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C.UTF-8",
                    "JAVA_HOME": str(self.jdk), "GRADLE_USER_HOME": str(self.root / "gradle-user"),
                    "ANDROID_HOME": str(self.sdk), "ANDROID_SDK_ROOT": str(self.sdk),
                    "ANDROID_USER_HOME": str(self.root / "android-user"),
                    "XDG_CACHE_HOME": str(self.root / "cache"),
                    "CYIME_RENDER_OUT": str(self.source / "app/build/lantype-ci-renders"),
                    **{key: str(self.root / "tmp") for key in ("TMPDIR", "TMP", "TEMP")}}
        # Java's per-user Maven/Robolectric caches also stay on the volume. This
        # is a JVM property, not a reassignment of the real HOME environment.
        self.env["JAVA_TOOL_OPTIONS"] = "-Djava.io.tmpdir=" + str(self.root / "tmp") + " -Duser.home=" + str(self.root / "java-user")
        self.env["PATH"] = os.pathsep.join((str(self.jdk / "bin"), str(self.sdk / "platform-tools"),
                                           str(self.sdk / "build-tools/36.0.0"), os.environ["PATH"]))
        for name in ("GH_TOKEN", "GITHUB_TOKEN"):
            self.env.pop(name, None)

    def volume_usage(self):
        require(os.path.ismount(self.root) and self.root.stat().st_dev != self.temporary.stat().st_dev,
                "Work root must be its independent mounted filesystem")
        require(stat.S_ISREG(self.volume.lstat().st_mode) and self.volume.stat().st_size == CAPACITY,
                "The owned volume image must be exactly 4608 MiB")
        info = os.statvfs(self.root)
        require(0 < info.f_blocks * info.f_frsize <= CAPACITY, "Mounted filesystem exceeds the work-volume limit")
        return filesystem_usage(self.root)

    def allocation(self, label, *, final=False):
        """Report named job directories and at most two child levels, never host tools."""
        require(re.fullmatch(r"[a-z0-9-]+", label), "Invalid allocation label")
        directories = [(name, self.root / name) for name in
                       ("source", "sdk", "gradle-user", "java-user", "android-user", "tmp", "cache", "evidence")
                       if (self.root / name).is_dir() and not (self.root / name).is_symlink()]
        row = {"volume": self.volume_usage(), "allocatedDirectories": MEASURE["measure"](directories, set()),
               "scope": "Allocated local bytes only; linked installed SDK/JDK inputs are not copied or charged again.",
               "detailScope": "Named directories and two child levels; groups overlap and must not be summed.",
               "detailLimits": {"groups": 64, "childrenPerGroup": 64}, "details": []}
        targets = ("source/.gradle", "source/app/build", "source/plugin-core/build", "source/vendor",
                   "gradle-user/caches", "gradle-user/wrapper", "java-user/.m2", "java-user/.robolectric")
        for relative in targets:
            target = self.root / relative
            if not target.exists() or target.is_symlink():
                continue
            require(target.is_dir() and target == target.resolve() and target.stat().st_dev == self.root.stat().st_dev,
                    "Allocation target left the owned volume")
            first = sorted(target.iterdir())
            parents = [(target, first)]
            parents += [(child, sorted(child.iterdir())) for child in first[:64]
                        if child.is_dir() and not child.is_symlink() and child.stat().st_dev == self.root.stat().st_dev]
            for parent, children in parents:
                if len(row["details"]) >= 64:
                    row["detailGroupsTruncated"] = True
                    break
                selected = [(str(child.relative_to(self.root)), child) for child in children[:64]
                            if not child.is_symlink() and (child.is_dir() or child.is_file())]
                row["details"].append({"directory": str(parent.relative_to(self.root)),
                    "childrenSeen": len(children), "childrenBeyondLimit": max(0, len(children) - 64),
                    "symlinksSkipped": sum(child.is_symlink() for child in children[:64]),
                    "measurement": MEASURE["measure"](selected, set())})
        destination = self.receipts / ("final-work-volume-allocation.json" if final else "allocation-" + label + ".json")
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(row, stream, indent=2, sort_keys=True)
            stream.write("\n")

    def prune_archives(self):
        self.budget("before-archive-prune")
        require(not self.active.exists() and (self.evidence / "sdk-overlay.json").is_file(),
                "Prepare the environment and finish restoration before archive pruning")
        history = self.receipts / "commands.jsonl"
        require(history.is_file() and not history.is_symlink() and history.stat().st_size <= 4 * MIB,
                "Missing command receipts")
        restores = [json.loads(line) for line in history.read_text().splitlines()]
        restores = [row for row in restores if row.get("label") == "restore-runtime"]
        require(len(restores) == 1 and restores[0].get("exitCode") == 0
                and restores[0].get("timedOut") is False and restores[0].get("storageReserveStop") is False,
                "The complete runtime restoration command must have succeeded")
        row = prune_runtime_archives(self.root, self.source, self.receipts / "runtime-archive-prune.json")
        print(json.dumps({"archivePruneSucceeded": row["ok"], "removedFileBytes": row["removedFileBytes"],
                          "observedFreedFilesystemBytes": row["observedFreedFilesystemBytes"]}), flush=True)
        self.budget("after-archive-prune")
        self.allocation("after-archive-prune")

    def budget(self, label, *, collecting=False):
        require(re.fullmatch(r"[a-z0-9-]+", label), "Invalid checkpoint label")
        row = {"checkpoint": label, "workVolumeImageBytes": CAPACITY, "outsideLimitBytes": OUTSIDE_LIMIT,
               "enforcement": "bounded-work-volume-plus-outside-volume-checkpoints",
               "wholeTaskHardQuota": False, "continuousWholeTaskPeakMeasured": False,
               "allocationMethod": "lstat.st_blocks * 512; global (device,inode) dedup; no symlink traversal",
               "limitations": "Only checkout, RUNNER_TEMP and this job's _actions code are measured outside the volume; between-checkpoint allocations are not bounded."}
        try:
            roots = [("checkout", REPO), ("runnerTemporary", self.temporary),
                     ("hostedJobActionsCode", self.temporary.parent / "_actions")]
            for _, path in roots:
                MEASURE["real_directory"](str(path), "Outside-volume measurement root")
            for index, (_, left) in enumerate(roots):
                for _, right in roots[index + 1:]:
                    require(not left.is_relative_to(right) and not right.is_relative_to(left), "Measurement roots overlap")
            row["volume"] = self.volume_usage()
            row["outsideVolume"] = MEASURE["measure"](roots, {self.volume, self.root})
            row["receiptAllowanceBytes"] = 65536
            row["passed"] = (row["outsideVolume"]["allocatedBytes"] + 65536 <= OUTSIDE_LIMIT
                             and (collecting or row["volume"]["availableBytes"] > WORK_RESERVE))
        except (OSError, ValueError) as error:
            row.update(passed=False, error=str(error))
        save(self.receipts / ("storage-" + label + ".json"), row)
        print(json.dumps(row), flush=True)
        require(row["passed"], "Storage checkpoint failed: " + label)

    def run(self, label, command, timeout, *, cwd=None):
        require(re.fullmatch(r"[a-z0-9-]+", label), "Invalid command label")
        require(1 <= timeout <= 1800, "Command timeout must be 1..1800 seconds")
        require(not self.active.exists(), "An earlier owned command has not been collected")
        command = [str(item) for item in command]
        out_path, err_path = (self.evidence / (label + suffix) for suffix in (".stdout.txt", ".stderr.txt"))
        initial = self.volume_usage()
        require(initial["availableBytes"] > WORK_RESERVE, "Less than 256 MiB work-volume reserve before command")
        peak, started = initial["usedBytes"], time.monotonic()
        process = None
        row = {"label": label, "command": command, "cwd": str(cwd or self.source),
               "timeoutSeconds": timeout, "workVolumeReserveBytes": WORK_RESERVE,
               "samplingSeconds": 0.25, "continuousPeakGuaranteed": False,
               "stdout": out_path.name, "stderr": err_path.name, "timedOut": False, "storageReserveStop": False}
        try:
            with out_path.open("xb") as out, err_path.open("xb") as err:
                process = subprocess.Popen(command, cwd=cwd or self.source, env=self.env, stdin=subprocess.DEVNULL,
                                           stdout=out, stderr=err, start_new_session=True)
                save(self.active, {"pid": process.pid, "startTicks": start_ticks(process.pid), "label": label})
                while process.poll() is None:
                    usage = self.volume_usage()
                    peak = max(peak, usage["usedBytes"])
                    row["timedOut"] = time.monotonic() - started >= timeout
                    row["storageReserveStop"] = usage["availableBytes"] <= WORK_RESERVE
                    if row["timedOut"] or row["storageReserveStop"]:
                        break
                    time.sleep(0.25)
        except BaseException as error:
            row["interruptedBy"] = type(error).__name__ + ": " + str(error)[:2048]
            raise
        finally:
            if process is not None:
                # This Popen created this process group; do not kill by name or
                # target a daemon/shared runner process outside that group.
                stop_group(process.pid)
                row["exitCode"] = process.wait()
                self.active.unlink(missing_ok=True)
            usage = self.volume_usage()
            row.update(elapsedSeconds=round(time.monotonic() - started, 3),
                       observedPeakWorkVolumeUsedBytes=max(peak, usage["usedBytes"]), volumeAfter=usage)
            with (self.receipts / "commands.jsonl").open("a") as stream:
                stream.write(json.dumps(row) + "\n")
            print(json.dumps(row), flush=True)
        require(not row["storageReserveStop"], "Command stopped at the 256 MiB reserve; inspect " + label + " logs")
        require(not row["timedOut"] and row.get("exitCode") == 0, "Command failed or timed out; inspect " + label + " logs")

    def prepare(self):
        self.budget("before-prepare")
        require(not self.source.exists() and not self.source.is_symlink(), "Source-copy destination already exists")
        require((REPO / ".git").is_dir() and not (REPO / ".git").is_symlink(), "A regular Actions checkout with .git is required")
        self.run("copy-checkout", ["cp", "-a", "--no-preserve=ownership", "--", REPO, self.source], 120, cwd=self.root)
        require((self.source / ".git").is_dir(), "Copied checkout lost its git metadata")
        self.run("source-identity", ["git", "rev-parse", "HEAD"], 30)
        head = (self.evidence / "source-identity.stdout.txt").read_text().strip()
        require(head == os.environ["GITHUB_SHA"], "Source-copy commit does not match the Actions run")
        save(self.evidence / "source-identity.json", {"commit": head, "originalCheckout": str(REPO),
             "buildCheckout": str(self.source), "gitMetadataCopied": True, "apkSigningPerformed": False})
        require(re.fullmatch(r"21(?:[.+-].*)?", properties(self.jdk / "release").get("JAVA_VERSION", "")), "Preinstalled JDK 21 is required")
        require((self.jdk / "bin/javac").is_file(), "Preinstalled javac is missing")
        required = {
            "platformTools": component(self.host_sdk / "platform-tools", ("adb",), ()),
            # Command-line tools use a real local metadata directory below;
            # unlike a borrowed package, an archive install need not have XML.
            "commandLineTools": component(self.host_sdk / "cmdline-tools/latest", ("bin/sdkmanager",), (), package_metadata=False)}
        optional = {
            "buildTools36": component(self.host_sdk / "build-tools/36.0.0", ("aapt", "aapt2", "zipalign", "apksigner", "d8"),
                                      ("lib/d8.jar", "lib/apksigner.jar"), expected="36.0.0"),
            "platform36": component(self.host_sdk / "platforms/android-36", (), ("android.jar",),
                                    key="AndroidVersion.ApiLevel", expected="36")}
        ndks = {path.name: component(path, ("toolchains/llvm/prebuilt/linux-x86_64/bin/clang",), (), expected=path.name)
                for path in sorted((self.host_sdk / "ndk").glob("*")) if re.fullmatch(r"\d+\.\d+\.\d+", path.name)}
        save(self.receipts / "sdk-input-inventory.json", {"hostSdk": str(self.host_sdk), "jdk": str(self.jdk),
             "required": required, "fixedPackages": optional, "installedNdks": ndks})
        require(all(row["usable"] for row in required.values()), "Required preinstalled SDK inputs are missing; inspect sdk-input-inventory.json")
        require(ndks.get(NDK, {}).get("usable"), "Required preinstalled NDK " + NDK + " is unavailable; no NDK download is allowed")
        require(not self.sdk.is_symlink() and self.sdk.is_dir() and not any(self.sdk.iterdir()), "SDK overlay must be empty")
        original, overlay = self.host_sdk / "cmdline-tools/latest", self.sdk / "cmdline-tools/latest"
        require((original / "lib").is_dir(), "Preinstalled sdkmanager libraries are missing")
        (overlay / "bin").mkdir(parents=True)
        shutil.copy2(original / "bin/sdkmanager", overlay / "bin/sdkmanager")
        for name in ("source.properties", "package.xml", "NOTICE.txt"):
            path = original / name
            if path.is_file():
                require(path.stat().st_size <= MIB, "SDK launcher metadata is unexpectedly large")
                shutil.copy2(path, overlay / name)
        (overlay / "lib").symlink_to(original / "lib", target_is_directory=True)
        licenses = sorted(path for path in (self.host_sdk / "licenses").glob("*") if path.is_file())
        require(licenses and sum(path.stat().st_size for path in licenses) <= MIB, "Preaccepted SDK licenses are unavailable or too large")
        (self.sdk / "licenses").mkdir()
        for path in licenses:
            shutil.copy2(path, self.sdk / "licenses" / path.name)
        # Keep all package-manager parent directories on the bounded volume.
        # Both application modes explicitly require the preinstalled NDK above.
        # Keeping ndk as a real parent also prevents any unexpected AGP package
        # install from writing through a parent link into the host SDK.
        for name in ("ndk", "platforms", "build-tools"):
            (self.sdk / name).mkdir()
        (self.sdk / "platform-tools").symlink_to(self.host_sdk / "platform-tools", target_is_directory=True)
        for version, row in ndks.items():
            if row["usable"]:
                (self.sdk / "ndk" / version).symlink_to(self.host_sdk / "ndk" / version, target_is_directory=True)
        selected = {}
        for name, relative, package in (("buildTools36", "build-tools/36.0.0", "build-tools;36.0.0"),
                                       ("platform36", "platforms/android-36", "platforms;android-36")):
            if optional[name]["usable"]:
                (self.sdk / relative).symlink_to(self.host_sdk / relative, target_is_directory=True)
                selected[name] = "preinstalled-package-link"
            else:
                self.run("sdk-install-" + name.lower(), [overlay / "bin/sdkmanager", "--sdk_root=" + str(self.sdk),
                         "--channel=0", "--verbose", package], 420)
                selected[name] = "official-sdkmanager-inside-work-volume"
        installed = {
            "buildTools36": component(self.sdk / "build-tools/36.0.0", ("aapt", "aapt2", "zipalign", "apksigner", "d8"),
                                      ("lib/d8.jar", "lib/apksigner.jar"), expected="36.0.0"),
            "platform36": component(self.sdk / "platforms/android-36", (), ("android.jar",), key="AndroidVersion.ApiLevel", expected="36")}
        require(all(row["usable"] for row in installed.values()), "Prepared fixed SDK packages are incomplete")
        save(self.evidence / "sdk-overlay.json", {"sdk": str(self.sdk), "selected": selected,
             "installed": installed, "linkedNdkVersions": [version for version, row in ndks.items() if row["usable"]],
             "wrapperAllowedDownloads": ["build-tools;36.0.0", "platforms;android-36"],
             "requiredPreinstalledNdk": NDK, "ndkDownloadAllowed": False,
             "agpSdkInstallRoot": str(self.sdk), "emulatorPrepared": False})
        self.budget("after-prepare")

    def collect(self):
        # If Actions interrupted the wrapper before its finally block, verify
        # the saved process identity before stopping only that owned group.
        if self.active.exists():
            row = json.loads(self.active.read_text())
            pid = int(row["pid"])
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                pass
            else:
                require(start_ticks(pid) == row["startTicks"] and os.getpgid(pid) == pid,
                        "Saved process identity changed; preserve the work volume")
                stop_group(pid)
            self.active.unlink()
        (self.root / "evidence-reserve.bin").unlink(missing_ok=True)
        # Never traverse ext4's root-owned lost+found or linked host SDK tools.
        self.allocation("final", final=True)
        self.budget("before-evidence-upload", collecting=True)


def interrupted(signum, frame):
    raise InterruptedError("Received signal " + str(signum))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("prepare", "execute", "budget", "prune-runtime-archives", "collect"))
    parser.add_argument("--label", default="initialized")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    driver = None
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        require(re.fullmatch(r"[a-z0-9-]+", args.label), "Invalid step label")
        require(1 <= args.timeout <= 1800, "Command timeout must be 1..1800 seconds")
        driver = Driver()
        if args.stage == "execute":
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            require(command and (driver.evidence / "sdk-overlay.json").is_file(), "Prepare the environment before executing an explicit command")
            driver.budget("before-" + args.label)
            try:
                driver.run(args.label, command, args.timeout)
            finally:
                if args.label in ("assemble-offline", "tests-and-renders"):
                    driver.allocation(args.label)
                driver.budget("after-" + args.label)
        elif args.stage == "budget":
            driver.budget(args.label)
        elif args.stage == "prepare":
            driver.prepare()
        elif args.stage == "prune-runtime-archives":
            driver.prune_archives()
        else:
            driver.collect()
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        row = {"stage": args.stage, "label": args.label, "error": str(error)[:4096], "scope": "offline-build-environment"}
        if driver is not None:
            if os.path.ismount(driver.root):
                row["volumeAfterFailure"] = driver.volume_usage()
            save(driver.receipts / ("failure-" + args.stage + "-" + args.label + ".json"), row)
        print(json.dumps(row), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
