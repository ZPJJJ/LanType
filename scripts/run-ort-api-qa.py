#!/usr/bin/env python3
"""Positive Android ORT API check, driven by ort-api-qa.yml on a hosted emulator.

The existing ort-api-smoke.c is compiled unchanged, with its main symbol renamed,
into a small ARM64/API 28 JNI library. Android instrumentation invokes it on its
own worker thread and saves its original stdout/stderr in the app's private files.
This is not a product APK, a standalone ARM executable test, an inference test,
or physical-device acceptance. There are no mock files, signal handlers,
sanitizers, fault injection, or host-native execution in this driver.

Heavy writes stay on the workflow's 4608 MiB filesystem. A separate 512 MiB
outside-volume checkpoint assertion is not a continuous whole-job hard quota.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import shutil
import signal
import stat
import subprocess
import sys
import time
import urllib.request
import zipfile

REPO = Path(__file__).resolve().parents[1]
REPOSITORY = "ZPJJJ/LanType"
PACKAGE = "app.lantype.ortapiqa"
AVD = "lantype-ort-api35"
IMAGE = "system-images;android-35;google_apis;x86_64"
NDK = "29.0.14206865"
MIB = 1024**2
WORK_RESERVE = 256 * MIB
LIMITATIONS = [
    "Only ordinary loading, C API 28, reported provider names and environment lifecycle are checked.",
    "Provider inference, models, keyboard input and product integration are not tested.",
    "The guest is API 35 x86_64 with ARM64 translation, not a physical ARM64 or 16 KiB device.",
    "The disposable debug certificate does not sign LanType and is not retained.",
]

MANIFEST = '''<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="app.lantype.ortapiqa" android:versionCode="1" android:versionName="1.0">
  <uses-sdk android:minSdkVersion="28" android:targetSdkVersion="35" />
  <application android:debuggable="true" android:allowBackup="false"
      android:extractNativeLibs="true" android:label="Disposable ORT API QA" />
  <instrumentation android:name="app.lantype.ortapiqa.Runner"
      android:targetPackage="app.lantype.ortapiqa" android:functionalTest="true" />
</manifest>
'''

JAVA = r'''package app.lantype.ortapiqa;
import android.app.Activity;
import android.app.Instrumentation;
import android.content.Context;
import android.os.Bundle;
import android.os.Looper;
import android.os.Process;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.json.JSONObject;

public final class Runner extends Instrumentation {
    private native int runProbe(String library, String stdout, String stderr);
    private static String sha256(File file) throws Exception {
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        try (FileInputStream in = new FileInputStream(file)) {
            byte[] buffer = new byte[65536];
            int count;
            while ((count = in.read(buffer)) != -1) hash.update(buffer, 0, count);
        }
        StringBuilder result = new StringBuilder();
        for (byte b : hash.digest()) result.append(String.format("%02x", b & 255));
        return result.toString();
    }
    private static void save(File file, JSONObject value) throws Exception {
        try (FileOutputStream out = new FileOutputStream(file)) {
            out.write((value.toString(2) + "\n").getBytes(StandardCharsets.UTF_8));
            out.getFD().sync();
        }
    }
    @Override public void onCreate(Bundle arguments) {
        super.onCreate(arguments);
        start(); // Android creates the dedicated instrumentation worker.
    }
    @Override public void onStart() {
        Context context = getTargetContext();
        File files = context.getFilesDir();
        File resultFile = new File(files, "runner-result.json");
        JSONObject result = new JSONObject();
        int code = Activity.RESULT_CANCELED;
        try {
            if (Thread.currentThread() == Looper.getMainLooper().getThread())
                throw new IllegalStateException("Probe must run on instrumentation worker");
            Thread.currentThread().setName("lantype-positive-ort-api");
            File library = new File(context.getApplicationInfo().nativeLibraryDir, "libonnxruntime.so");
            File probe = new File(context.getApplicationInfo().nativeLibraryDir, "liblantype_ort_smoke_jni.so");
            result.put("schemaVersion", 1).put("started", true).put("returnedNormally", false)
                .put("pid", Process.myPid()).put("is64Bit", Process.is64Bit())
                .put("thread", Thread.currentThread().getName())
                .put("libraryPath", library.getAbsolutePath()).put("librarySha256", sha256(library))
                .put("probeSha256", sha256(probe));
            save(resultFile, result);
            System.loadLibrary("lantype_ort_smoke_jni");
            int exit = runProbe(library.getAbsolutePath(), new File(files, "probe-stdout.jsonl").getAbsolutePath(),
                new File(files, "probe-stderr.txt").getAbsolutePath());
            result.put("returnedNormally", true).put("probeExitCode", exit);
            save(resultFile, result);
            if (exit == 0) code = Activity.RESULT_OK;
        } catch (Throwable error) {
            try { result.put("javaError", error.toString()); save(resultFile, result); }
            catch (Exception writeError) { writeError.printStackTrace(); }
            error.printStackTrace();
        }
        Bundle bundle = new Bundle();
        bundle.putString("resultFile", resultFile.getAbsolutePath());
        bundle.putString("scope", "positive-load-api-environment-only");
        finish(code, bundle);
    }
}
'''

JNI = r'''#include <jni.h>
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
extern int lantype_ort_smoke_main(int, char **);
JNIEXPORT jint JNICALL Java_app_lantype_ortapiqa_Runner_runProbe(
    JNIEnv *env, jobject self, jstring library, jstring output, jstring errors) {
  (void)self;
  const char *lib = NULL, *out = NULL, *err = NULL;
  int out_fd = -1, err_fd = -1, saved_out = -1, saved_err = -1, code = 90;
  lib = (*env)->GetStringUTFChars(env, library, NULL);
  if (lib == NULL) goto cleanup;
  out = (*env)->GetStringUTFChars(env, output, NULL);
  if (out == NULL) goto cleanup;
  err = (*env)->GetStringUTFChars(env, errors, NULL);
  if (err == NULL) goto cleanup;
  out_fd = open(out, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
  err_fd = open(err, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
  if (out_fd < 0 || err_fd < 0) goto cleanup;
  fflush(NULL);
  saved_out = dup(STDOUT_FILENO); saved_err = dup(STDERR_FILENO);
  if (saved_out < 0 || saved_err < 0) goto cleanup;
  if (dup2(out_fd, STDOUT_FILENO) < 0 || dup2(err_fd, STDERR_FILENO) < 0) goto cleanup;
  char *arguments[] = {"lantype-ort-api-smoke", (char *)lib, NULL};
  code = lantype_ort_smoke_main(2, arguments);
  fflush(NULL);
  if (fsync(out_fd) != 0 || fsync(err_fd) != 0) code = 91;
cleanup:
  if (saved_out >= 0) { if (dup2(saved_out, STDOUT_FILENO) < 0) code = 92; close(saved_out); }
  if (saved_err >= 0) { if (dup2(saved_err, STDERR_FILENO) < 0) code = 93; close(saved_err); }
  if (out_fd >= 0) close(out_fd);
  if (err_fd >= 0) close(err_fd);
  if (lib != NULL) (*env)->ReleaseStringUTFChars(env, library, lib);
  if (out != NULL) (*env)->ReleaseStringUTFChars(env, output, out);
  if (err != NULL) (*env)->ReleaseStringUTFChars(env, errors, err);
  return code;
}
'''


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def tool_component(directory, executables=(), files=(), *, metadata="source.properties",
                   revision_key="Pkg.Revision", expected_revision=None):
    """Read a named tool inventory without executing a compiler or SDK tool."""
    directory = Path(directory)
    record = {"directory": str(directory), "resolvedDirectory": str(directory.resolve()),
              "checks": [], "errors": []}
    for relative, executable in [(name, True) for name in executables] + [(name, False) for name in files]:
        path = directory / relative
        usable = path.is_file() and (not executable or os.access(path, os.X_OK))
        record["checks"].append({"path": str(path), "executableRequired": executable, "usable": usable})
        if not usable:
            record["errors"].append("Missing " + ("executable: " if executable else "file: ") + str(path))
    path = directory / metadata
    try:
        require(path.stat().st_size <= MIB, "Tool metadata is unexpectedly large: " + str(path))
        properties = dict(line.split("=", 1) for line in path.read_text().splitlines()
                          if "=" in line and not line.lstrip().startswith("#"))
        properties = {key.strip(): value.strip().strip('"') for key, value in properties.items()}
        record.update(metadataSha256=digest(path), revision=properties.get(revision_key))
        if not record["revision"] or expected_revision is not None and record["revision"] != expected_revision:
            record["errors"].append(f"Unexpected {revision_key} in {path}: {record['revision']!r}; expected {expected_revision!r}")
    except (OSError, ValueError) as error:
        record["errors"].append(str(error))
    record["usable"] = not record["errors"]
    return record


class Driver:
    def __init__(self):
        self.root = Path(os.environ["QA_ROOT"])
        self.receipts = Path(os.environ["QA_RECEIPTS"])
        temporary = Path(os.environ["RUNNER_TEMP"])
        require(self.root == temporary / "lantype-ort-api-work", "Unexpected work root")
        require(self.receipts == temporary / "lantype-ort-api-receipts", "Unexpected receipt root")
        require(not self.root.is_symlink() and not self.receipts.is_symlink(), "Symlink root refused")
        self.evidence = self.root / "evidence"
        self.candidate = self.root / "candidate"
        self.build = self.root / "build"
        self.host_sdk = Path(os.environ.get("ORT_QA_HOST_SDK", os.environ.get("ANDROID_HOME", "/missing-sdk")))
        self.sdk = self.root / "sdk"
        self.tools_marker = self.root / "sdk-tools-ready.json"
        self.jdk = Path(os.environ.get("JAVA_HOME", "/missing-jdk"))
        self.serial = os.environ.get("ANDROID_SERIAL", "emulator-5554")
        require(self.serial == "emulator-5554", "This workflow accepts only its owned hosted emulator")
        self.env = {**os.environ, "PATH": str(self.jdk / "bin") + os.pathsep + os.environ.get("PATH", ""),
                    "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1", "JAVA_HOME": str(self.jdk),
                    "ANDROID_HOME": str(self.sdk), "ANDROID_SDK_ROOT": str(self.sdk),
                    "ANDROID_USER_HOME": str(self.root / "android-user"),
                    "ANDROID_EMULATOR_HOME": str(self.root / "android-user"),
                    "ANDROID_AVD_HOME": str(self.root / "avd"),
                    "XDG_CACHE_HOME": str(self.root / "cache"),
                    **{key: str(self.root / "tmp") for key in ("TMPDIR", "TMP", "TEMP")}}
        self.env["JAVA_TOOL_OPTIONS"] = (self.env.get("JAVA_TOOL_OPTIONS", "") +
                                          " -Djava.io.tmpdir=" + str(self.root / "tmp")).strip()
        # Ubuntu's libpulse0 also loads libpulsecommon from its private
        # pulseaudio subdirectory. Keep both paths in every stage/process,
        # including the separately started guest and product QA wrapper.
        loader = self.root / "host-libs/usr/lib/x86_64-linux-gnu"
        self.env["LD_LIBRARY_PATH"] = os.pathsep.join(dict.fromkeys((
            str(loader), str(loader / "pulseaudio"),
            *filter(None, self.env.get("LD_LIBRARY_PATH", "").split(os.pathsep)))))
        for key in ("GH_TOKEN", "GITHUB_TOKEN"):
            self.env.pop(key, None)  # Native/tool subprocesses never need a GitHub token.
        self.counter = 0

    def tool_inventory(self, sdk):
        sdk = Path(sdk)
        components = {
            "jdk21": tool_component(self.jdk, ("bin/java", "bin/javac", "bin/keytool"),
                                    metadata="release", revision_key="JAVA_VERSION"),
            "ndk29": tool_component(sdk / "ndk" / NDK,
                tuple("toolchains/llvm/prebuilt/linux-x86_64/bin/" + name for name in
                      ("aarch64-linux-android28-clang", "llvm-readelf")), expected_revision=NDK),
            "commandLineTools": tool_component(sdk / "cmdline-tools/latest", ("bin/sdkmanager", "bin/avdmanager")),
            "platformTools": tool_component(sdk / "platform-tools", ("adb",)),
            "buildTools36": tool_component(sdk / "build-tools/36.0.0", ("aapt", "aapt2", "d8", "zipalign", "apksigner"),
                                           ("lib/d8.jar", "lib/apksigner.jar"), expected_revision="36.0.0"),
            "platform36": tool_component(sdk / "platforms/android-36", files=("android.jar",),
                                         revision_key="AndroidVersion.ApiLevel", expected_revision="36"),
            "emulator": tool_component(sdk / "emulator", ("emulator",)),
        }
        java = components["jdk21"]
        if not re.fullmatch(r"21(?:[.+-].*)?", java.get("revision") or ""):
            java["errors"].append("A preinstalled JDK 21 is required; no JDK download is permitted")
            java["usable"] = False
        commands = components["commandLineTools"]
        if not (sdk / "cmdline-tools/latest/lib").is_dir():
            commands["errors"].append("Missing preinstalled command-line tool libraries")
            commands["usable"] = False
        license_dir = sdk / "licenses"
        licenses = sorted(path for path in license_dir.glob("*") if path.is_file())
        license_ok = bool(licenses) and sum(path.stat().st_size for path in licenses) <= MIB
        components["licenses"] = {"directory": str(license_dir), "usable": license_ok,
            "files": [{"name": path.name, "sha256": digest(path)} for path in licenses] if license_ok else [],
            "errors": [] if license_ok else ["Missing or unexpectedly large preaccepted SDK licenses: " + str(license_dir)]}
        return {"schemaVersion": 1, "sdk": str(sdk), "hostSdk": str(self.host_sdk),
                "jdk": str(self.jdk), "components": components}

    def require_tools(self):
        require(self.tools_marker.is_file() and not self.tools_marker.is_symlink(),
                "SDK overlay is not ready; run --stage tools before build/image/run")
        require(self.tools_marker.stat().st_size <= MIB, "SDK overlay marker is unexpectedly large")
        marker = json.loads(self.tools_marker.read_text())
        inventory = self.tool_inventory(self.sdk)
        require(marker.get("schemaVersion") == 1 and marker.get("inventory") == inventory and
                all(row["usable"] for row in inventory["components"].values()),
                "SDK overlay/tool identity changed after preparation; inspect sdk-tools-ready.json")
        return inventory

    def capture_ndk_inputs(self):
        """Keep actual installed notices and static C++ archive identities only."""
        ndk = self.host_sdk / "ndk" / NDK
        toolchain = ndk / "toolchains/llvm/prebuilt/linux-x86_64"
        output = self.evidence / "ndk-source-inputs"
        notices = [ndk / "source.properties", *sorted(set([ndk / "NOTICE", ndk / "NOTICE.toolchain",
                                                          *toolchain.glob("NOTICE*")]))]
        copied, rows = 0, []
        for path in notices:
            row = {"path": str(path), "present": path.is_file(), "copied": False}
            if path.is_file():
                require(path.resolve().is_relative_to(ndk.resolve()), "NDK notice points outside its installed NDK")
                size = path.stat().st_size
                row.update(bytes=size, sha256=digest(path))
                if copied + size <= 4 * MIB:
                    target = output / path.relative_to(ndk)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
                    copied += size
                    row.update(copied=True, evidencePath=str(target.relative_to(self.evidence)))
                else:
                    row["reason"] = "Notice copies exceed the 4 MiB evidence allowance; identity retained only"
                    print(row["reason"] + ": " + str(path), flush=True)
            rows.append(row)
        library_root = toolchain / "sysroot/usr/lib/aarch64-linux-android"
        archives = []
        for name in ("libc++_static.a", "libc++abi.a"):
            matches = sorted(library_root.rglob(name)) if library_root.is_dir() else []
            require(len(matches) <= 64, "Unexpectedly many NDK static archive matches")
            if not matches:
                archives.append({"name": name, "present": False})
            for path in matches:
                require(path.is_file() and path.resolve().is_relative_to(ndk.resolve()),
                        "Unexpected NDK static archive path: " + str(path))
                archives.append({"name": name, "path": str(path), "present": True,
                                 "bytes": path.stat().st_size, "sha256": digest(path), "copied": False})
        save(self.evidence / "ndk-source-inputs.json", {"schemaVersion": 1, "ndkRevision": NDK,
             "ndkRoot": str(ndk), "noticeCopyLimitBytes": 4 * MIB, "copiedNoticeBytes": copied,
             "notices": rows, "staticArchiveSearchRoot": str(library_root), "staticArchives": archives,
             "scope": "Installed NDK metadata/notices and AArch64 static archive identity; not a complete source distribution."})

    def tools(self):
        self.budget("before-tools")
        before = self.tool_inventory(self.host_sdk)
        save(self.receipts / "tool-inventory-before.json", before)
        print(json.dumps(before), flush=True)
        fixed = ("jdk21", "ndk29", "commandLineTools", "platformTools", "licenses")
        failures = {name: before["components"][name]["errors"] for name in fixed
                    if not before["components"][name]["usable"]}
        require(not failures, "Required preinstalled tools unavailable (automatic replacement forbidden): " + json.dumps(failures))
        self.capture_ndk_inputs()
        if self.tools_marker.exists():
            self.require_tools()
            self.budget("tools-rechecked")
            return
        require(not self.sdk.is_symlink() and (not self.sdk.exists() or not any(self.sdk.iterdir())),
                "Incomplete or unknown SDK overlay; preserve evidence and use a fresh bounded work volume")
        self.sdk.mkdir(exist_ok=True)
        # Only launchers and small metadata are copied; the installed tool jars
        # and NDK/platform-tools payloads are reused. Licenses are small copies,
        # so a package manager can never write through them into the host SDK.
        original = self.host_sdk / "cmdline-tools/latest"
        overlay = self.sdk / "cmdline-tools/latest"
        (overlay / "bin").mkdir(parents=True)
        for name in ("sdkmanager", "avdmanager"):
            shutil.copy2(original / "bin" / name, overlay / "bin" / name)
        for name in ("source.properties", "package.xml", "NOTICE.txt"):
            if (original / name).is_file():
                shutil.copy2(original / name, overlay / name)
        (overlay / "lib").symlink_to(original / "lib", target_is_directory=True)
        (self.sdk / "licenses").mkdir()
        for row in before["components"]["licenses"]["files"]:
            shutil.copy2(self.host_sdk / "licenses" / row["name"], self.sdk / "licenses" / row["name"])
        (self.sdk / "ndk").mkdir()
        for relative in ("ndk/" + NDK, "platform-tools"):
            (self.sdk / relative).symlink_to(self.host_sdk / relative, target_is_directory=True)
        selected = {}
        for name, relative, package in (("buildTools36", "build-tools/36.0.0", "build-tools;36.0.0"),
                ("platform36", "platforms/android-36", "platforms;android-36"), ("emulator", "emulator", "emulator")):
            if before["components"][name]["usable"]:
                (self.sdk / relative).parent.mkdir(parents=True, exist_ok=True)
                (self.sdk / relative).symlink_to(self.host_sdk / relative, target_is_directory=True)
                selected[name] = "preinstalled-link"
            else:
                self.run("sdk-install-" + name, [overlay / "bin/sdkmanager", "--sdk_root=" + str(self.sdk),
                         "--channel=0", "--verbose", package], timeout=420)
                selected[name] = "official-sdkmanager-stable-channel"
        after = self.tool_inventory(self.sdk)
        save(self.receipts / "tool-inventory-after.json", after)
        failures = {name: row["errors"] for name, row in after["components"].items() if not row["usable"]}
        require(not failures, "Prepared SDK tools are incomplete: " + json.dumps(failures))
        require(self.tool_inventory(self.host_sdk) == before, "Preinstalled SDK/JDK metadata changed during overlay preparation")
        self.budget("after-tools")
        save(self.tools_marker, {"schemaVersion": 1, "inventory": after, "selectedComponents": selected,
                                "allowedDownloads": ["build-tools;36.0.0", "platforms;android-36", "emulator"]})
        shutil.copy2(self.tools_marker, self.evidence / "sdk-tools-ready.json")

    def parameters(self):
        values = {key: os.environ[key] for key in ("CANDIDATE_RUN_ID", "CANDIDATE_HEAD",
                  "CANDIDATE_ARTIFACT_ID", "CANDIDATE_MANIFEST_SHA256")}
        require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY, "Only ZPJJJ/LanType is supported")
        for key in ("CANDIDATE_RUN_ID", "CANDIDATE_ARTIFACT_ID"):
            require(re.fullmatch(r"[1-9][0-9]{0,19}", values[key]), "Invalid numeric " + key)
        require(re.fullmatch(r"[0-9a-f]{40}", values["CANDIDATE_HEAD"]), "Expected full lowercase candidate commit")
        require(re.fullmatch(r"[0-9a-f]{64}", values["CANDIDATE_MANIFEST_SHA256"]), "Expected lowercase manifest SHA-256")
        return values

    def volume_usage(self):
        info = os.statvfs(self.root)
        return {"capacityBytes": info.f_blocks * info.f_frsize,
                "usedBytes": (info.f_blocks - info.f_bfree) * info.f_frsize,
                "availableBytes": info.f_bavail * info.f_frsize}

    def budget(self, checkpoint):
        require(re.fullmatch(r"[a-z0-9-]+", checkpoint), "Invalid checkpoint")
        self.receipts.mkdir(parents=True, exist_ok=True)
        result = {"schemaVersion": 1, "checkpoint": checkpoint,
                  "workVolumeCapacityBytes": 4608 * MIB, "overheadLimitBytes": 512 * MIB,
                  "wholeTaskHardQuota": False, "continuousWholeTaskPeakMeasured": False,
                  "enforcement": "bounded-work-volume-plus-outside-volume-checkpoints",
                  "allocationMethod": "lstat.st_blocks * 512; global (device,inode) dedup; no symlink traversal"}
        try:
            temporary = Path(os.environ["RUNNER_TEMP"])
            volume = Path(os.environ["QA_VOLUME"])
            require(volume == temporary / "lantype-ort-api-volume.img", "Unexpected volume image")
            require(stat.S_ISREG(volume.lstat().st_mode), "Volume image must be a regular file")
            require(volume.stat().st_size == 4608 * MIB, "Unexpected work-volume image size")
            require(os.path.ismount(self.root), "Work root is not its bounded mounted volume")
            require(self.root.stat().st_dev != temporary.stat().st_dev, "Work root is on host filesystem")
            module = runpy.run_path(str(REPO / "scripts/check-ort-build-overhead.py"))
            roots = [("checkout", Path(os.environ["GITHUB_WORKSPACE"])),
                     ("runnerTemporary", temporary), ("hostedJobActionsCode", temporary.parent / "_actions")]
            for _, path in roots:
                module["real_directory"](str(path), "Overhead root")
            measured = module["measure"](roots, {volume, self.root})
            result.update(outsideVolume=measured, volume=self.volume_usage(), receiptAllowanceBytes=65536)
            result["passed"] = measured["allocatedBytes"] + 65536 <= 512 * MIB
        except (OSError, ValueError, KeyError) as error:
            result.update(passed=False, error=str(error))
        save(self.receipts / ("storage-" + checkpoint + ".json"), result)
        print(json.dumps(result), flush=True)
        require(result["passed"], "Storage checkpoint failed: " + checkpoint)
        return result

    def run(self, label, command, *, timeout=120, check=True, input_text=None, cwd=None, copy_stdout_to=None):
        """Keep full stdout/stderr and exit status; sample volume use while running."""
        self.counter += 1
        prefix = f"{os.environ.get('ORT_QA_STAGE', 'step')}-{self.counter:03d}-{label}"
        out_path, err_path = (self.evidence / (prefix + suffix) for suffix in (".stdout.txt", ".stderr.txt"))
        command = [str(item) for item in command]
        peak = self.volume_usage()["usedBytes"]
        started = time.monotonic()
        with out_path.open("wb") as out, err_path.open("wb") as err:
            process = subprocess.Popen(command, stdout=out, stderr=err, stdin=subprocess.PIPE if input_text else subprocess.DEVNULL,
                                       env=self.env, cwd=cwd or self.root, start_new_session=True)
            if input_text:
                process.stdin.write(input_text.encode())
                process.stdin.close()
            timed_out = False
            budget_stop = False
            while process.poll() is None:
                usage = self.volume_usage()
                peak = max(peak, usage["usedBytes"])
                timed_out = time.monotonic() - started > timeout
                budget_stop = usage["availableBytes"] <= WORK_RESERVE and os.environ.get("ORT_QA_STAGE") != "collect"
                if timed_out or budget_stop:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(0.25)
            code = process.wait()
        peak = max(peak, self.volume_usage()["usedBytes"])
        record = {"command": command, "exitCode": code, "timedOut": timed_out,
                  "storageReserveStop": budget_stop, "workVolumeReserveBytes": WORK_RESERVE,
                  "stdout": out_path.name, "stderr": err_path.name,
                  "elapsedSeconds": round(time.monotonic() - started, 3),
                  "observedPeakWorkVolumeUsedBytes": peak, "samplingSeconds": 0.25,
                  "continuousPeakGuaranteed": False}
        # Small command receipts survive even if the bounded filesystem fills.
        with (self.receipts / "commands.jsonl").open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        print(json.dumps({key: record[key] for key in ("command", "exitCode", "timedOut", "observedPeakWorkVolumeUsedBytes")}), flush=True)
        require(not budget_stop, "Command stopped with less than 256 MiB work-volume reserve; see " + prefix)
        require(not check or (code == 0 and not timed_out), "Command failed; see " + prefix)
        if code == 0 and not timed_out and copy_stdout_to is not None:
            shutil.copyfile(out_path, copy_stdout_to)  # Preserve original probe bytes.
        return out_path.read_text(errors="replace"), code

    def adb(self, label, *arguments, **kwargs):
        return self.run(label, [self.sdk / "platform-tools/adb", "-s", self.serial, *arguments], **kwargs)

    def identity(self):
        values = self.parameters()
        token = os.environ.get("GH_TOKEN")
        require(token, "GitHub read token is needed only for candidate identity")

        def fetch(resource):
            request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + resource,
                headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                         "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "LanType-positive-ORT-QA"})
            with urllib.request.urlopen(request, timeout=45) as response:
                require(response.status == 200, "GitHub identity response failed")
                body = response.read(2 * MIB + 1)
                require(len(body) <= 2 * MIB, "Identity response exceeds limit")
                return json.loads(body)

        run = fetch("/actions/runs/" + values["CANDIDATE_RUN_ID"])
        artifact = fetch("/actions/artifacts/" + values["CANDIDATE_ARTIFACT_ID"])
        save(self.evidence / "github-candidate-run.json", run)
        save(self.evidence / "github-candidate-artifact.json", artifact)
        require(str(run["id"]) == values["CANDIDATE_RUN_ID"], "Run ID mismatch")
        require(run["head_sha"] == values["CANDIDATE_HEAD"], "Run head mismatch")
        require(run["path"] == ".github/workflows/native-ort-build.yml", "Wrong source workflow")
        require(run["event"] == "workflow_dispatch" and run["head_branch"] == "main", "Expected manually dispatched main build")
        require(run["head_repository"]["full_name"] == REPOSITORY, "Foreign source repository")
        require(run["status"] == "completed" and run["conclusion"] == "success", "Native build is not completed successfully")
        require(str(artifact["id"]) == values["CANDIDATE_ARTIFACT_ID"] and not artifact["expired"], "Unavailable artifact")
        require(artifact["name"] == f"lantype-ort-candidate-{run['id']}-{run['run_attempt']}", "Wrong candidate artifact name or attempt")
        require(artifact["workflow_run"]["id"] == run["id"] and artifact["workflow_run"]["head_sha"] == run["head_sha"], "Artifact source mismatch")
        require(0 < artifact["size_in_bytes"] <= 256 * MIB, "Candidate artifact is unexpectedly large")
        save(self.evidence / "candidate-request.json", {**values, "repository": REPOSITORY,
             "artifactName": artifact["name"], "runAttempt": run["run_attempt"],
             "qaWorkflowCommit": os.environ["GITHUB_SHA"], "qaRunId": os.environ["GITHUB_RUN_ID"]})
        self.budget("candidate-identity")

    def verify_candidate(self):
        values = self.parameters()
        request = json.loads((self.evidence / "candidate-request.json").read_text())
        require(all(request[key] == value for key, value in values.items()), "Candidate request changed after API identity check")
        manifest_path = self.candidate / "candidate-manifest.json"
        require(stat.S_ISREG(manifest_path.lstat().st_mode), "Manifest is not a regular file")
        require(digest(manifest_path) == values["CANDIDATE_MANIFEST_SHA256"], "Candidate manifest SHA-256 mismatch")
        manifest = json.loads(manifest_path.read_text())
        require(manifest["schemaVersion"] == 1 and manifest["kind"] == "unsigned-native-candidate", "Unexpected manifest kind")
        require(manifest["workflowCommit"] == values["CANDIDATE_HEAD"] and str(manifest["runId"]) == values["CANDIDATE_RUN_ID"], "Manifest source mismatch")
        require(manifest["runtimeVersion"] == "1.28.0" and manifest["abi"] == "arm64-v8a" and manifest["minSdk"] == 28, "Wrong runtime target")
        require(manifest["applicationIntegrated"] is False and manifest["androidRuntimeAccepted"] is False, "Unexpected candidate acceptance claim")
        declared = {}
        for row in manifest["files"]:
            relative = PurePosixPath(row["path"])
            require(not relative.is_absolute() and ".." not in relative.parts and str(relative) == row["path"], "Unsafe manifest path")
            require(row["path"] not in declared and row["path"] != "candidate-manifest.json", "Duplicate/self-listed manifest entry")
            require(type(row["bytes"]) is int and row["bytes"] >= 0 and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "Malformed manifest entry")
            declared[row["path"]] = row
        actual = set()
        for path in self.candidate.rglob("*"):
            mode = path.lstat().st_mode
            require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), "Candidate symlink or special file refused")
            if stat.S_ISREG(mode) and path != manifest_path:
                relative = path.relative_to(self.candidate).as_posix()
                require(relative in declared, "Unlisted candidate file: " + relative)
                require(path.stat().st_size == declared[relative]["bytes"] and digest(path) == declared[relative]["sha256"], "Candidate file hash/size mismatch: " + relative)
                actual.add(relative)
        require(actual == set(declared), "Candidate manifest inventory is incomplete")
        probe = REPO / "tools/lantype-device-qa/ort-api-smoke.c"
        require(digest(self.candidate / "ort-api-smoke.c") == digest(probe), "Candidate C probe differs from the reviewed QA probe")
        library = self.candidate / "lib/arm64-v8a/libonnxruntime.so"
        self.run("static-elf-abi", [sys.executable, REPO / "scripts/verify-ort-abi.py", "--library", library,
                                  "--output", self.evidence / "candidate-abi.json"])
        identity = {**request, "manifestSha256": digest(manifest_path), "librarySha256": digest(library),
                    "libraryBytes": library.stat().st_size, "probeSourceSha256": digest(probe),
                    "inventoryFileCount": len(actual), "scope": "static-candidate-identity"}
        save(self.evidence / "candidate-identity.json", identity)
        shutil.copy2(manifest_path, self.evidence / "candidate-manifest.json")
        return identity

    def build_apk(self):
        self.require_tools()
        self.budget("before-build")
        identity = self.verify_candidate()
        source = self.evidence / "test-app-source"
        source.mkdir()
        (source / "AndroidManifest.xml").write_text(MANIFEST)
        (source / "Runner.java").write_text(JAVA)
        (source / "probe-jni.c").write_text(JNI)
        shutil.copy2(REPO / "tools/lantype-device-qa/ort-api-smoke.c", source / "ort-api-smoke.c")
        for name in ("classes", "dex", "lib/arm64-v8a"):
            (self.build / name).mkdir(parents=True, exist_ok=True)
        ndk = self.sdk / "ndk" / NDK
        require("Pkg.Revision = " + NDK in (ndk / "source.properties").read_text(), "NDK revision mismatch")
        shutil.copy2(ndk / "source.properties", self.evidence / "ndk-source.properties")
        tools = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin"
        clang = tools / "aarch64-linux-android28-clang"
        native = self.build / "lib/arm64-v8a/liblantype_ort_smoke_jni.so"
        self.run("compiler-version", [clang, "--version"])
        self.run("jni-build", [clang, "-shared", "-fPIC", "-O2", "-fvisibility=hidden", "-Dmain=lantype_ort_smoke_main",
            "-I", self.candidate / "include", source / "ort-api-smoke.c", source / "probe-jni.c",
            "-Wl,-z,defs", "-Wl,-z,max-page-size=16384", "-Wl,-soname,liblantype_ort_smoke_jni.so", "-ldl", "-o", native])
        self.run("jni-elf", [tools / "llvm-readelf", "-h", "-d", "--wide", native])
        build_tools = self.sdk / "build-tools/36.0.0"
        android = self.sdk / "platforms/android-36/android.jar"
        unsigned, aligned, apk = (self.build / name for name in ("unsigned.apk", "aligned.apk", "ort-positive-qa.apk"))
        self.run("aapt-link", [build_tools / "aapt2", "link", "-I", android, "--manifest", source / "AndroidManifest.xml", "-o", unsigned])
        self.run("javac", [self.jdk / "bin/javac", "--release", "17", "-encoding", "UTF-8", "-classpath", android,
                           "-d", self.build / "classes", source / "Runner.java"])
        self.run("d8", [build_tools / "d8", "--lib", android, "--min-api", "28", "--output", self.build / "dex",
                        *sorted((self.build / "classes").rglob("*.class"))])
        with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(self.build / "dex/classes.dex", "classes.dex")
            archive.write(native, "lib/arm64-v8a/liblantype_ort_smoke_jni.so")
            archive.write(self.candidate / "lib/arm64-v8a/libonnxruntime.so", "lib/arm64-v8a/libonnxruntime.so")
        key = self.build / "disposable-qa-only.jks"
        try:
            self.run("disposable-key", [self.jdk / "bin/keytool", "-genkeypair", "-keystore", key, "-storepass", "android",
                "-keypass", "android", "-alias", "qa", "-dname", "CN=Disposable ORT API QA", "-keyalg", "RSA",
                "-keysize", "2048", "-validity", "2", "-noprompt"])
            key.chmod(0o600)
            self.run("zipalign", [build_tools / "zipalign", "-f", "4", unsigned, aligned])
            self.run("debug-sign", [build_tools / "apksigner", "sign", "--ks", key, "--ks-pass", "pass:android",
                "--key-pass", "pass:android", "--out", apk, aligned])
        finally:
            key.unlink(missing_ok=True)
        self.run("debug-apk-certificate", [build_tools / "apksigner", "verify", "--print-certs", apk])
        permissions, _ = self.run("debug-apk-permissions", [build_tools / "aapt2", "dump", "permissions", apk])
        require("uses-permission" not in permissions, "Disposable APK must request no Android permissions")
        identity.update(apkSha256=digest(apk), apkBytes=apk.stat().st_size, probeLibrarySha256=digest(native),
                        ndkRevision=NDK, nativeTarget="aarch64-linux-android28", disposableTestApk=True,
                        productSigned=False, jniWrapperSha256=digest(source / "probe-jni.c"),
                        javaRunnerSha256=digest(source / "Runner.java"), limitations=LIMITATIONS)
        save(self.evidence / "test-apk-identity.json", identity)
        unsigned.unlink()
        aligned.unlink()
        self.budget("after-build")

    def image(self):
        self.require_tools()
        self.budget("before-image")
        sdk = self.sdk
        overlay = sdk / "cmdline-tools/latest"
        # Do not install host packages outside the accounted work volume.
        loader = self.root / "host-libs"
        loader.mkdir()
        loader_path = loader / "usr/lib/x86_64-linux-gnu"
        self.env["LD_LIBRARY_PATH"] = os.pathsep.join(filter(None, (str(loader_path), self.env.get("LD_LIBRARY_PATH", ""))))
        _, code = self.run("emulator-loader-preflight", [self.sdk / "emulator/emulator", "-version"], check=False)
        if code:
            self.run("emulator-loader-download", ["apt-get", "download", "libpulse0", "libasyncns0"], cwd=loader)
            for deb in sorted(loader.glob("*.deb")):
                self.run("emulator-loader-unpack", ["dpkg-deb", "-x", deb, loader])
            self.run("emulator-version", [self.sdk / "emulator/emulator", "-version"])
        self.run("kvm-accel-check", [self.sdk / "emulator/emulator", "-accel-check"])
        self.run("sdk-image-install", [overlay / "bin/sdkmanager", "--sdk_root=" + str(sdk), IMAGE], timeout=660)
        image_root = sdk / "system-images/android-35/google_apis/x86_64"
        shutil.copy2(image_root / "source.properties", self.evidence / "system-image.properties")
        self.run("create-avd", [overlay / "bin/avdmanager", "create", "avd", "--force", "--name", AVD,
            "--package", IMAGE, "--device", "pixel_2"], input_text="no\n")
        config_path = self.root / "avd" / (AVD + ".avd/config.ini")
        config = {}
        for line in config_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
        config.update({"image.sysdir.1": str(image_root) + "/", "disk.dataPartition.size": "2G",
                       "hw.sdCard": "no", "fastboot.forceColdBoot": "yes", "fastboot.forceFastBoot": "no"})
        config_path.write_text("".join(key + "=" + value + "\n" for key, value in sorted(config.items())))
        shutil.copy2(config_path, self.evidence / "avd-config.ini")
        self.budget("after-image")

    def run_guest(self):
        self.require_tools()
        self.budget("before-guest")
        require(not (self.root / "emulator.pid").exists(), "Emulator has already been started")
        devices, _ = self.run("adb-devices-before", [self.sdk / "platform-tools/adb", "devices"])
        require(not re.search(r"^" + re.escape(self.serial) + r"\s", devices, re.M), "Selected emulator serial already exists")
        self.env.update(ANDROID_HOME=str(self.root / "sdk"), ANDROID_SDK_ROOT=str(self.root / "sdk"),
                        LD_LIBRARY_PATH=os.pathsep.join(filter(None, (str(self.root / "host-libs/usr/lib/x86_64-linux-gnu"),
                                                                     self.env.get("LD_LIBRARY_PATH", "")))))
        command = [str(self.sdk / "emulator/emulator"), "-avd", AVD, "-port", "5554", "-accel", "on",
                   "-cores", "4", "-memory", "3072", "-gpu", "swiftshader", "-no-window", "-no-audio",
                   "-no-boot-anim", "-no-snapshot", "-wipe-data", "-no-metrics"]
        with (self.evidence / "emulator.stdout.txt").open("wb") as out, (self.evidence / "emulator.stderr.txt").open("wb") as err:
            process = subprocess.Popen(command, stdout=out, stderr=err, env=self.env, cwd=self.root, start_new_session=True)
        (self.root / "emulator.pid").write_text(str(process.pid) + "\n")
        save(self.evidence / "emulator-command.json", {"command": command, "pid": process.pid})
        self.adb("wait-for-device", "wait-for-device", timeout=120)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            require(process.poll() is None, "Emulator exited before guest boot")
            boot, _ = self.adb("boot-completed", "shell", "getprop", "sys.boot_completed", timeout=10, check=False)
            users, _ = self.adb("boot-users", "shell", "dumpsys", "user", timeout=10, check=False)
            if boot.strip() == "1" and "RUNNING_UNLOCKED" in users:
                break
            time.sleep(3)
        else:
            raise ValueError("Guest did not reach boot complete with an unlocked user")
        properties, _ = self.adb("guest-properties", "shell", "getprop")
        props = dict(re.findall(r"^\[([^]]+)\]: \[(.*)\]$", properties, re.M))
        require(props.get("ro.build.version.sdk") == "35", "Expected API 35 guest")
        require("x86_64" in props.get("ro.product.cpu.abilist", "").split(",") and
                "arm64-v8a" in props.get("ro.product.cpu.abilist", "").split(","), "Expected x86_64 guest with ARM64 ABI")
        require(props.get("ro.dalvik.vm.native.bridge") not in (None, "", "0"), "Guest has no native bridge")
        page_size, _ = self.adb("page-size", "shell", "getconf", "PAGESIZE")
        save(self.evidence / "guest-identity.json", {"serial": self.serial, "apiLevel": 35,
             "fingerprint": props.get("ro.build.fingerprint"), "abiList": props.get("ro.product.cpu.abilist"),
             "nativeBridge": props.get("ro.dalvik.vm.native.bridge"), "pageSize": int(page_size.strip()),
             "physicalDevice": False, "executionPath": "ARM64 APK instrumentation JNI", "shellArm64ExecutableAssumed": False})
        pre, _ = self.adb("pre-test-logcat", "logcat", "-d", "-b", "all")
        require(not re.search(r"WATCHDOG KILLING SYSTEM PROCESS|FATAL EXCEPTION IN SYSTEM PROCESS", pre), "Framework failed before test")
        self.adb("airplane-mode", "shell", "cmd", "connectivity", "airplane-mode", "enable")
        self.adb("wifi-off", "shell", "svc", "wifi", "disable")
        self.adb("data-off", "shell", "svc", "data", "disable")
        self.adb("mobile-data-setting", "shell", "settings", "put", "global", "mobile_data", "0")
        network = {}
        for _ in range(10):
            network = {key: self.adb("network-confirm-" + key, "shell", "settings", "get", "global", key)[0].strip()
                       for key in ("airplane_mode_on", "wifi_on", "mobile_data")}
            if network == {"airplane_mode_on": "1", "wifi_on": "0", "mobile_data": "0"}:
                break
            time.sleep(1)
        save(self.evidence / "network-before-test.json", network)
        self.adb("network-connectivity", "shell", "dumpsys", "connectivity")
        require(network == {"airplane_mode_on": "1", "wifi_on": "0", "mobile_data": "0"}, "Guest radio settings were not disabled before test launch")
        self.adb("install-disposable-apk", "install", "--abi", "arm64-v8a", str(self.build / "ort-positive-qa.apk"))
        package, _ = self.adb("installed-test-package", "shell", "dumpsys", "package", PACKAGE)
        require("primaryCpuAbi=arm64-v8a" in package, "Test APK was not selected as ARM64")
        self.adb("clear-logcat", "logcat", "-c")
        with (self.evidence / "test-live-logcat.txt").open("wb") as out:
            logcat = subprocess.Popen([str(self.sdk / "platform-tools/adb"), "-s", self.serial, "logcat", "-b", "all", "-v", "threadtime"],
                                      stdout=out, stderr=subprocess.STDOUT, env=self.env, cwd=self.root, start_new_session=True)
        (self.root / "logcat.pid").write_text(str(logcat.pid) + "\n")
        instrument, code = self.adb("instrument-positive-api", "shell", "am", "instrument", "-w", "-r", "--abi", "arm64-v8a",
                                    PACKAGE + "/.Runner", timeout=240, check=False)
        self.read_app_files()
        runner = json.loads((self.evidence / "app-runner-result.json").read_text())
        expected = json.loads((self.evidence / "test-apk-identity.json").read_text())
        require(code == 0 and "INSTRUMENTATION_CODE: -1" in instrument, "Instrumentation did not finish successfully")
        require(runner.get("returnedNormally") is True and runner.get("probeExitCode") == 0, "C main did not return successfully")
        require(runner.get("is64Bit") is True and runner.get("thread") == "lantype-positive-ort-api", "Wrong probe execution context")
        require(runner.get("librarySha256") == expected["librarySha256"] and
                runner.get("probeSha256") == expected["probeLibrarySha256"], "Installed native library identity mismatch")
        rows = [json.loads(line) for line in (self.evidence / "app-probe-stdout.jsonl").read_text().splitlines() if line.strip()]
        summaries = [row for row in rows if row.get("event") == "summary"]
        require(len(summaries) == 1 and summaries[0].get("passed") is True and summaries[0].get("apiVersion") == 28,
                "Probe has no unique successful C API 28 summary")
        require(all(row.get("probe") == "lantype-ort-api-smoke" and row.get("state") != "failed" for row in rows), "Probe reported a failed stage")
        save(self.evidence / "result.json", {"schemaVersion": 1, "status": "passed", "scope": "positive-load-api-environment-only",
             "candidateRunId": expected["CANDIDATE_RUN_ID"], "candidateCommit": expected["CANDIDATE_HEAD"],
             "candidateManifestSha256": expected["manifestSha256"], "librarySha256": expected["librarySha256"],
             "mainReturnedNormally": True, "probeExitCode": 0, "probeSummary": summaries[0], "limitations": LIMITATIONS})
        self.budget("after-guest")

    def read_app_files(self):
        for remote, local in (("runner-result.json", "app-runner-result.json"), ("probe-stdout.jsonl", "app-probe-stdout.jsonl"),
                              ("probe-stderr.txt", "app-probe-stderr.txt")):
            self.adb("run-as-" + remote.replace(".", "-"), "exec-out", "run-as", PACKAGE, "cat", "files/" + remote,
                     check=False, timeout=15, copy_stdout_to=self.evidence / local)

    def stop_owned_process(self, name, required_tokens):
        pid_path = self.root / (name + ".pid")
        if not pid_path.is_file():
            return
        pid = int(pid_path.read_text().strip())
        proc = Path("/proc") / str(pid) / "cmdline"
        if not proc.exists():
            return
        arguments = proc.read_bytes().split(b"\0")
        require(all(token.encode() in arguments for token in required_tokens), "Refusing to stop unrelated " + name + " PID")
        require(os.getpgid(pid) == pid, "Owned process group identity changed")
        os.killpg(pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while proc.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        if proc.exists():
            os.killpg(pid, signal.SIGKILL)

    def collect(self):
        if not os.path.ismount(self.root):
            return
        (self.root / "evidence-reserve.bin").unlink(missing_ok=True)
        if (self.root / "emulator.pid").is_file():
            # All reads concern this fresh disposable test guest/package.
            for label, command in (("final-logcat", ["logcat", "-d", "-b", "all"]),
                 ("final-users", ["shell", "dumpsys", "user"]),
                 ("test-exit-info", ["shell", "dumpsys", "activity", "exit-info", PACKAGE]),
                 ("native-app-dropbox", ["shell", "dumpsys", "dropbox", "--print", "data_app_native_crash"]),
                 ("native-system-tombstone", ["shell", "dumpsys", "dropbox", "--print", "SYSTEM_TOMBSTONE"])):
                try:
                    self.adb(label, *command, timeout=15, check=False)
                except (OSError, ValueError) as error:
                    print("Diagnostic unavailable: " + str(error), file=sys.stderr)
            try:
                self.read_app_files()
            finally:
                self.stop_owned_process("logcat", ["-s", self.serial, "logcat"])
                self.stop_owned_process("emulator", ["-avd", AVD])
        self.budget("after-collection")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("budget", "tools", "identity", "build", "image", "run", "collect"))
    parser.add_argument("--checkpoint", default="manual")
    args = parser.parse_args()
    os.environ["ORT_QA_STAGE"] = args.stage
    driver = None
    try:
        driver = Driver()
        if args.stage == "budget":
            driver.budget(args.checkpoint)
        else:
            require(args.stage == "collect" or os.path.ismount(driver.root), "Work root must be the bounded volume")
            {"tools": driver.tools, "identity": driver.identity, "build": driver.build_apk, "image": driver.image,
             "run": driver.run_guest, "collect": driver.collect}[args.stage]()
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        failure = {"schemaVersion": 1, "status": "failed", "stage": args.stage,
                   "error": str(error), "scope": "positive-load-api-environment-only", "limitations": LIMITATIONS}
        if driver is not None:
            try:
                save(driver.receipts / ("failure-" + args.stage + ".json"), failure)
                if os.path.ismount(driver.root):
                    (driver.root / "evidence-reserve.bin").unlink(missing_ok=True)
                    failure["volumeAfterFailure"] = driver.volume_usage()
                    save(driver.evidence / "result.json", failure)
            except OSError as write_error:
                print("Could not save all failure evidence: " + str(write_error), file=sys.stderr)
        print(json.dumps(failure), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
