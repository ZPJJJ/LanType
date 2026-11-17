#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise fixed releases or a locked signed candidate on disposable Android.

Only standard adb commands are used. Every touch is derived from a newly dumped
UI hierarchy; missing/ambiguous accessibility nodes are evidence, not permission
to guess a coordinate. This script does not clear app data or seed private files.
The legacy upgrade remains the default. Candidate modes separately cover a fresh
install with same-candidate data retention, or replacement of uninitialized 1.1.1;
neither mode claims migration of initialized old-version user data.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET


CS_TEMPLATE = 'Debug.Log("{{cursor}}"); // {{date}}'
LUA_TEMPLATE = 'print("{{cursor}}") -- {{date}}'
SAVED = (
    "已将模板原文保存在本机；展开的选区和剪贴板不会自动保存。",
    "Template saved locally. Expanded selection and clipboard text are not saved automatically.",
)
WIZARD_TITLE = "澜语 · 中文 / English (US)"
BOUNDS = re.compile(r"^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$")
RELEASE_SPEC = importlib.util.spec_from_file_location(
    "lantype_release_inputs", Path(__file__).with_name("fetch-release-apks.py"))
RELEASES = importlib.util.module_from_spec(RELEASE_SPEC)
RELEASE_SPEC.loader.exec_module(RELEASES)


class SmokeFailure(RuntimeError):
    pass


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_release_certificate(signature: str) -> str:
    """Accept one original release signer using the observed SDK 36/37 labels."""
    counts = re.findall(r"^Number of signers: (\d+)\s*$", signature, re.M)
    lines = [line.strip() for line in signature.splitlines() if "certificate SHA-256 digest:" in line]
    match = re.fullmatch(r"(?:Signer #1|V3\.0 Signer:) certificate SHA-256 digest: ([0-9a-fA-F]{64})",
                         lines[0]) if len(lines) == 1 else None
    if counts != ["1"] or match is None or match[1].lower() != RELEASES.CERT_SHA256:
        raise SmokeFailure("APK signer does not match the established single LanType release certificate")
    return match[1].lower()


def slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")[:80]


def bounds(node: ET.Element) -> tuple[int, int, int, int] | None:
    match = BOUNDS.fullmatch(node.get("bounds", ""))
    if not match:
        return None
    left, top, right, bottom = map(int, match.groups())
    return (left, top, right, bottom) if right > left and bottom > top else None


def labels(node: ET.Element) -> set[str]:
    return {node.get("text", "").strip(), node.get("content-desc", "").strip()} - {""}


def component(package: str, name: str) -> str:
    if name.startswith("."):
        name = package + name
    if not re.fullmatch(r"[A-Za-z0-9_.$]+", package + name):
        raise SmokeFailure("Unexpected APK component name")
    return f"{package}/{name}"


def ime_from_manifest(xmltree: str, package: str) -> str:
    """Read the actual BIND_INPUT_METHOD service, not a guessed class name."""
    services = []
    lines = xmltree.splitlines()
    for index, line in enumerate(lines):
        start = re.match(r"^(\s*)E: service\b", line)
        if not start:
            continue
        indent = len(start[1])
        block = []
        for child in lines[index + 1:]:
            element = re.match(r"^(\s*)E:", child)
            if element and len(element[1]) <= indent:
                break
            block.append(child)
        text = "\n".join(block)
        if '"android.permission.BIND_INPUT_METHOD"' not in text:
            continue
        name = re.search(r'android:name\([^)]*\)="([^"]+)"', text)
        if name and '"android.view.InputMethod"' in text:
            services.append(component(package, name[1]))
    if len(services) != 1:
        raise SmokeFailure(f"Expected one declared IME service, found {services!r}")
    return services[0]


def choose_node(root: ET.Element, names=(), *, package=None, resource_id=None,
                enabled=True) -> ET.Element | None:
    found = []
    for node in root.iter("node"):
        if package and node.get("package") != package:
            continue
        if resource_id and node.get("resource-id") != resource_id:
            continue
        if names and not labels(node).intersection(names):
            continue
        if not bounds(node) or (enabled and node.get("enabled") == "false"):
            continue
        found.append(node)
    # Some dumps repeat a merged semantic node at exactly the same bounds.
    unique = {bounds(node): node for node in found}
    if len(unique) > 1:
        raise SmokeFailure(f"Ambiguous UI selector {names or resource_id}: {list(unique)}")
    return next(iter(unique.values()), None)


def qwerty_key(root: ET.Element, package: str, letter: str) -> ET.Element:
    """Use visible letter nodes and verify all three observed QWERTY rows.

    Candidates may contain a single letter too. The bottommost letter nodes must
    form a complete, ordered QWERTY grid before any one of them may be tapped.
    No screen resolution, key size, testTag or fixed position is assumed.
    """
    selected = {}
    for char in "abcdefghijklmnopqrstuvwxyz":
        nodes = [node for node in root.iter("node")
                 if node.get("package") == package and bounds(node)
                 and char in {value.lower() for value in labels(node)}
                 and node.get("enabled") != "false"]
        if not nodes:
            raise SmokeFailure(f"Accessible QWERTY key {char!r} is missing")
        nodes.sort(key=lambda node: (bounds(node)[1] + bounds(node)[3],
                                    -(bounds(node)[2] - bounds(node)[0])), reverse=True)
        selected[char] = nodes[0]
    previous_y = -1.0
    for row in ("qwertyuiop", "asdfghjkl", "zxcvbnm"):
        boxes = [bounds(selected[char]) for char in row]
        xs = [(box[0] + box[2]) / 2 for box in boxes]
        ys = [(box[1] + box[3]) / 2 for box in boxes]
        tolerance = max(box[3] - box[1] for box in boxes)
        if xs != sorted(set(xs)) or max(ys) - min(ys) > tolerance or min(ys) <= previous_y:
            raise SmokeFailure("Visible letters do not form an unambiguous QWERTY grid")
        previous_y = max(ys)
    return selected[letter]


class Smoke:
    def __init__(self, args):
        self.args = args
        self.mode = getattr(args, "mode", "legacy-upgrade")
        self.candidate_lock = None
        if self.mode != "legacy-upgrade":
            lock_path = getattr(args, "candidate_lock", None)
            if lock_path is None:
                raise SmokeFailure("--candidate-lock is required; no latest APK is selected")
            try:
                self.candidate_lock = RELEASES.load_candidate_lock(lock_path)
            except RELEASES.DownloadError as error:
                raise SmokeFailure(str(error)) from error
        self.output = args.output.resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        if (self.output / "result.json").exists():
            raise SmokeFailure("Use a new output directory; existing device evidence is not overwritten")
        self.adb_path = shutil.which("adb")
        sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        if not self.adb_path and sdk:
            self.adb_path = str(Path(sdk) / "platform-tools/adb")
        self.aapt = shutil.which("aapt")
        if not self.aapt and sdk:
            candidates = list((Path(sdk) / "build-tools").glob("*/aapt"))
            if candidates:
                self.aapt = str(max(candidates, key=lambda path: tuple(
                    int(n) for n in re.findall(r"\d+", path.parent.name))))
        if not self.adb_path or not self.aapt:
            raise SmokeFailure("adb and aapt are required (PATH or ANDROID_HOME)")
        self.serial = args.serial or os.environ.get("ANDROID_SERIAL") or "emulator-5554"
        if not re.fullmatch(r"emulator-\d+", self.serial):
            raise SmokeFailure("This automatic workflow accepts emulator-* serials only")
        self.device_authorized = False
        self.sequence = 0
        self.command_sequence = 0
        self.current = None
        self.report = {
            "schema": 1, "started_utc": utc(), "status": "running", "cases": [],
            "scope": "Unmodified release APK upgrade on a disposable Android; shell-assisted IME enable/select; real accessible keyboard touches.",
            "not_covered": [
                "Physical ARM64 device performance, battery use or 16 KiB runtime compatibility",
                "Legacy private-directory conflict migration (no private files are injected)",
                "Tool-cabin private copy/cut, clipboard history and process-restart privacy (not run by this core smoke)",
            ],
        }
        if self.mode != "legacy-upgrade":
            self.report.update(mode=self.mode,
                scope=("Fresh signed candidate functionality followed by same-candidate reinstall and retention of data created by that candidate."
                       if self.mode == "fresh-candidate" else
                       "Replace fixed installed 1.1.1 without launching or initializing it, then initialize and exercise the signed candidate."),
                candidate_lock={"path": str(args.candidate_lock.resolve()),
                                "sha256": RELEASES.file_sha256(args.candidate_lock), "identity": self.candidate_lock},
                old_user_data_migration_tested=False,
                same_candidate_data_retention_tested=False)
            self.report["not_covered"].append("Migration of initialized old-version user data; no old user fixture is created in these modes")
        self.save()

    def save(self):
        temporary = self.output / "result.json.tmp"
        temporary.write_text(json.dumps(self.report, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(self.output / "result.json")

    def command(self, argv, *, timeout=60, check=True, binary=False):
        self.command_sequence += 1
        started = time.monotonic()
        entry = {"id": self.command_sequence, "utc": utc(), "argv": [str(v) for v in argv]}
        try:
            process = subprocess.run(entry["argv"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     timeout=timeout, check=False)
            entry.update(exit_code=process.returncode,
                         stderr=process.stderr.decode("utf-8", "replace"),
                         stdout_bytes=len(process.stdout))
            if not binary:
                entry["stdout"] = process.stdout.decode("utf-8", "replace")
        except subprocess.TimeoutExpired as error:
            entry.update(error="timeout", timeout_seconds=timeout)
            raise SmokeFailure(f"Command timed out: {' '.join(entry['argv'])}") from error
        finally:
            entry["duration_seconds"] = round(time.monotonic() - started, 3)
            with (self.output / "commands.jsonl").open("a") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if check and process.returncode:
            raise SmokeFailure(f"Command exited {process.returncode}: {' '.join(entry['argv'])}\n{entry['stderr'][-1200:]}\n{entry.get('stdout', '')[-1200:]}")
        return process.stdout if binary else process.stdout.decode("utf-8", "replace")

    def adb(self, *args, **kwargs):
        return self.command([self.adb_path, "-s", self.serial, *args], **kwargs)

    def snapshot(self, name):
        self.sequence += 1
        stem = f"{self.sequence:04d}-{slug(name)}"
        remote = f"/sdcard/lantype-smoke-{os.getpid()}-{self.sequence}.xml"
        self.adb("shell", "uiautomator", "dump", remote, timeout=45)
        xml = self.adb("exec-out", "cat", remote, binary=True)
        (self.output / f"{stem}.xml").write_bytes(xml)
        png = self.adb("exec-out", "screencap", "-p", binary=True)
        (self.output / f"{stem}.png").write_bytes(png)
        self.adb("shell", "rm", remote, check=False)
        if self.current is not None:
            self.current["evidence"].append({"xml": f"{stem}.xml", "screenshot": f"{stem}.png"})
            self.save()
        try:
            return ET.fromstring(xml)
        except ET.ParseError as error:
            raise SmokeFailure(f"UI hierarchy is not valid XML: {stem}.xml") from error

    def touch(self, node, *, hold=False):
        left, top, right, bottom = bounds(node)
        x, y = (left + right) // 2, (top + bottom) // 2
        if hold:
            self.adb("shell", "input", "swipe", str(x), str(y), str(x), str(y), "700")
        else:
            self.adb("shell", "input", "tap", str(x), str(y))

    def scroll(self, root, direction):
        nodes = [node for node in root.iter("node") if node.get("package") == self.package
                 and node.get("scrollable") == "true" and bounds(node)
                 and "Horizontal" not in node.get("class", "")]
        if not nodes:
            return False
        # Compose exposes vertical/horizontal ScrollViews; reject ambiguity.
        vertical = [node for node in nodes if node.get("class", "").endswith(".ScrollView")]
        nodes = vertical or nodes
        if len(nodes) != 1:
            raise SmokeFailure("Cannot identify one vertical scroll container from fresh XML")
        left, top, right, bottom = bounds(nodes[0])
        x = (left + right) // 2
        lower, upper = top + (bottom - top) * 3 // 4, top + (bottom - top) // 4
        start, end = (lower, upper) if direction == "down" else (upper, lower)
        self.adb("shell", "input", "swipe", str(x), str(start), str(x), str(end), "400")
        return True

    def find(self, name, names=(), *, package=None, resource_id=None, scroll=None,
             timeout=15, enabled=True):
        deadline, scrolls = time.monotonic() + timeout, 0
        while True:
            root = self.snapshot(name)
            node = choose_node(root, names, package=package, resource_id=resource_id, enabled=enabled)
            if node is not None:
                return root, node
            if scroll and scrolls < 3 and self.scroll(root, scroll):
                scrolls += 1
            elif time.monotonic() >= deadline:
                raise SmokeFailure(f"UI control not found: {names or resource_id}; no guessed-coordinate fallback")
            else:
                time.sleep(1)

    def tap(self, name, names=(), *, package=None, resource_id=None, scroll=None, hold=False):
        _, node = self.find(name, names, package=package or self.package,
                            resource_id=resource_id, scroll=scroll)
        self.touch(node, hold=hold)

    def expect_text(self, name, value, *, scroll=None):
        # Assertions can match more than one visible occurrence; actions cannot.
        deadline, scrolls = time.monotonic() + 15, 0
        while True:
            root = self.snapshot(name)
            # A clickable Compose source card can merge its heading and value
            # into newline-separated accessibility text. Require the exact
            # full value or exact line, never an arbitrary substring.
            if any(node.get("package") == self.package
                   and (value in labels(node) or value in node.get("text", "").splitlines())
                   and bounds(node) for node in root.iter("node")):
                return
            if scroll and scrolls < 3 and self.scroll(root, scroll):
                scrolls += 1
            elif time.monotonic() >= deadline:
                raise SmokeFailure(f"Expected visible product text was not found: {value!r}")
            else:
                time.sleep(1)

    def diagnostic(self, name):
        for label, args in (("input-method", ("shell", "dumpsys", "input_method")),
                            ("window", ("shell", "dumpsys", "window", "windows")),
                            ("crash", ("logcat", "-d", "-b", "crash", "-t", "300")),
                            ("logcat", ("logcat", "-d", "-t", "1200"))):
            try:
                (self.output / f"{slug(name)}-{label}.txt").write_text(self.adb(*args, timeout=30, check=False))
            except Exception as error:
                (self.output / f"{slug(name)}-{label}-error.txt").write_text(str(error))

    def case(self, name, action, *, requires=True, required=True):
        record = {"name": name, "required": required, "started_utc": utc(), "evidence": []}
        self.report["cases"].append(record)
        self.current = record
        self.save()
        if not requires:
            record.update(status="blocked", reason="A prerequisite case did not pass")
        else:
            try:
                detail = action()
                record.update(status="passed", observed=detail)
            except Exception as error:
                record.update(status="failed", reason=f"{type(error).__name__}: {error}")
                if self.device_authorized:
                    try:
                        self.snapshot(name + "-failure")
                    except Exception as capture_error:
                        record["capture_error"] = str(capture_error)
                    self.diagnostic(name)
        record["finished_utc"] = utc()
        self.current = None
        self.save()
        print(f"{name}: {record['status']}", flush=True)
        return record["status"] == "passed"

    def apk(self, path, *, ime=False):
        path = path.resolve(strict=True)
        text = self.command([self.aapt, "dump", "badging", path])
        info = re.search(r"^package: name='([^']+)' versionCode='([^']+)' versionName='([^']*)'", text, re.M)
        if not info:
            raise SmokeFailure(f"Cannot read APK identity: {path}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        result = {"path": str(path), "bytes": path.stat().st_size, "sha256": digest.hexdigest(),
                  "package": info[1], "version_code": int(info[2]), "version_name": info[3]}
        if ime:
            tree = self.command([self.aapt, "dump", "xmltree", path, "AndroidManifest.xml"])
            result["ime"] = ime_from_manifest(tree, info[1])
        return result

    def verify_release_apk(self, info, expected, role):
        pairs = {"package": "package", "version_code": "versionCode", "version_name": "versionName",
                 "sha256": "sha256", "bytes": "size"}
        if any(info[key] != expected[field] for key, field in pairs.items()):
            raise SmokeFailure(role + " APK differs from its fixed signed identity")
        if Path(info["path"]).name != expected.get("fileName", expected.get("name")):
            raise SmokeFailure(role + " APK filename differs from its fixed identity")
        signer = shutil.which("apksigner") or str(Path(self.aapt).with_name("apksigner"))
        signature = self.command([signer, "verify", "--verbose", "--print-certs", info["path"]])
        evidence = role + "-signature.txt"
        (self.output / evidence).write_text(signature)
        certificate = require_release_certificate(signature)
        if certificate != expected["certificateSha256"]:
            raise SmokeFailure(role + " certificate differs from the explicit lock")
        info.update(certificate_sha256=certificate, signature_evidence=evidence)
        return info

    def environment(self):
        devices = self.command([self.adb_path, "devices", "-l"])
        ready = [line.split()[0] for line in devices.splitlines()[1:]
                 if len(line.split()) > 1 and line.split()[1] == "device"]
        if self.serial not in ready:
            raise SmokeFailure(f"Selected adb device {self.serial!r} is not ready")
        props = {name: self.adb("shell", "getprop", name).strip() for name in (
            "ro.build.version.sdk", "ro.build.version.release", "ro.build.fingerprint",
            "ro.product.model", "ro.product.cpu.abilist", "ro.product.cpu.abilist64",
            "ro.dalvik.vm.native.bridge", "ro.enable.native.bridge.exec", "sys.boot_completed", "ro.kernel.qemu")}
        current_user = self.adb("shell", "am", "get-current-user").strip()
        users = self.adb("shell", "dumpsys", "user")
        (self.output / "preflight-users.txt").write_text(users)
        result = {"serial": self.serial, "properties": props,
                  "page_size": self.adb("shell", "getconf", "PAGESIZE", check=False).strip(),
                  "current_user": current_user, "users_evidence": "preflight-users.txt"}
        self.report["environment"] = result
        if props["sys.boot_completed"] != "1":
            raise SmokeFailure("Guest has not completed boot")
        if props["ro.kernel.qemu"] != "1" or current_user != "0":
            raise SmokeFailure("Automatic radio/install actions require an emulator running Android user 0")
        user_zero = re.search(r"UserInfo\{0:.*?(?=\n\s*UserInfo\{|\Z)", users, re.S)
        if not user_zero or "RUNNING_UNLOCKED" not in user_zero[0]:
            raise SmokeFailure("Android user 0 has not reached RUNNING_UNLOCKED")
        self.device_authorized = True
        if self.mode == "legacy-upgrade":
            old, new, host = self.apk(self.args.old_apk, ime=True), self.apk(self.args.new_apk, ime=True), self.apk(self.args.host_apk)
            if old["package"] != new["package"] or old["ime"] != new["ime"] or new["version_code"] <= old["version_code"]:
                raise SmokeFailure("APK pair must have the same package/IME and an increasing versionCode")
        else:
            abis = props["ro.product.cpu.abilist"].split(",")
            if props["ro.build.version.sdk"] != "35" or "arm64-v8a" not in abis or "x86_64" not in abis or props["ro.dalvik.vm.native.bridge"] in ("", "0"):
                raise SmokeFailure("Candidate modes require the API 35 x86_64 emulator with its actual ARM64 native bridge")
            new = self.verify_release_apk(self.apk(self.args.new_apk, ime=True), self.candidate_lock, "candidate")
            host = self.apk(self.args.host_apk)
            old = None
            if self.mode == "replace-uninitialized":
                old = self.verify_release_apk(self.apk(self.args.old_apk, ime=True), RELEASES.BASELINE_1_1_1, "uninitialized-baseline")
                if old["package"] != new["package"] or old["ime"] != new["ime"] or new["version_code"] <= old["version_code"]:
                    raise SmokeFailure("The locked candidate must replace fixed 1.1.1 with the same package/IME and a greater versionCode")
        if host["package"] != "app.lantype.testhost" or host["package"] == new["package"]:
            raise SmokeFailure("Expected the separate LanType synthetic editor host")
        self.old, self.new, self.host = old, new, host
        self.package, self.host_package, self.ime = new["package"], host["package"], new["ime"]
        self.report["apks"] = {"new": new, "host": host}
        if old is not None:
            self.report["apks"]["old"] = old
        return result

    def network(self):
        self.adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
        self.adb("shell", "wm", "dismiss-keyguard")
        self.adb("shell", "cmd", "connectivity", "airplane-mode", "enable")
        self.adb("shell", "svc", "wifi", "disable")
        self.adb("shell", "svc", "data", "disable")
        self.adb("shell", "settings", "put", "global", "mobile_data", "0")
        actual = {}
        for _ in range(10):
            actual = {key: self.adb("shell", "settings", "get", "global", key).strip()
                      for key in ("airplane_mode_on", "wifi_on", "mobile_data")}
            if actual == {"airplane_mode_on": "1", "wifi_on": "0", "mobile_data": "0"}:
                break
            time.sleep(1)
        (self.output / "network-connectivity.txt").write_text(self.adb("shell", "dumpsys", "connectivity"))
        (self.output / "network-wifi.txt").write_text(self.adb("shell", "dumpsys", "wifi"))
        self.snapshot("network-disabled-before-product-install")
        if actual != {"airplane_mode_on": "1", "wifi_on": "0", "mobile_data": "0"}:
            raise SmokeFailure(f"Radio-setting readback failed: {actual}")
        return {"settings_readback": actual, "scope": "Radio settings plus dumpsys evidence; not a packet capture"}

    def installed_version(self, info):
        dump = self.adb("shell", "dumpsys", "package", info["package"])
        code = re.search(r"\bversionCode=(\d+)", dump)
        name = re.search(r"\bversionName=([^\r\n]+)", dump)
        if not code or int(code[1]) != info["version_code"] or not name or name[1].strip() != info["version_name"]:
            raise SmokeFailure(f"Installed package version differs from APK: {info['package']}")
        return {"version_code": int(code[1]), "version_name": name[1].strip()}

    def install(self, info, *, replace=True):
        flags = ("-r",) if replace else ()
        output = self.adb("install", "--streaming", "--no-incremental", *flags, info["path"], timeout=420)
        if "Success" not in output:
            raise SmokeFailure(f"Streaming install did not report success: {output}")
        return self.installed_version(info)

    def baseline_install(self):
        if "package:" in self.adb("shell", "pm", "path", self.package, check=False):
            raise SmokeFailure("Baseline requires a fresh disposable guest; existing product data will not be cleared")
        old = self.install(self.old)
        host = self.install(self.host)
        self.snapshot("baseline-installed")
        return {"old": old, "host": host}

    def package_state(self, name):
        dump = self.adb("shell", "dumpsys", "package", self.package)
        (self.output / (slug(name) + "-package.txt")).write_text(dump)
        fields = {}
        for field in ("userId", "dataDir", "ceDataInode", "firstInstallTime", "lastUpdateTime", "versionCode", "versionName"):
            match = re.search(r"\b" + field + r"=([^\n]+)", dump)
            if match:
                fields[field] = match[1].strip()
        return fields

    def require_same_installation(self, before, after):
        # UID/path/time corroborate package replacement; they do not prove old
        # private-data migration. The visible new-version fixture is separate.
        fields = ("userId", "dataDir", "firstInstallTime")
        if any(not before.get(key) or before[key] != after.get(key) for key in fields):
            raise SmokeFailure("Package replacement did not retain its public installation identity")

    def candidate_install(self):
        for info in (self.new, self.host):
            if "package:" in self.adb("shell", "pm", "path", info["package"], check=False):
                raise SmokeFailure("Candidate modes require a fresh guest; existing packages will not be cleared")
        if self.mode == "fresh-candidate":
            installed = self.install(self.new, replace=False)
            detail = {"candidate": installed, "candidate_was_first_product_apk": True}
        else:
            # Do not call launch(), onboarding(), select_ime() or create any
            # old-version fixture between these two installations.
            baseline = self.install(self.old, replace=False)
            before = self.package_state("uninitialized-baseline-installed")
            if self.adb("shell", "pidof", self.package, check=False).strip():
                raise SmokeFailure("Fixed baseline unexpectedly has a running process before replacement")
            installed = self.install(self.new, replace=True)
            after = self.package_state("uninitialized-baseline-replaced")
            self.require_same_installation(before, after)
            detail = {"baseline": baseline, "candidate": installed,
                      "old_app_launched_by_qa": False, "old_onboarding_completed_by_qa": False,
                      "old_user_fixture_created": False, "old_user_data_migration_tested": False,
                      "before": before, "after": after,
                      "scope": "Package replacement of an installed, uninitialized baseline; candidate setup still runs for the first time"}
        detail["host"] = self.install(self.host, replace=False)
        self.snapshot("candidate-mode-installed-before-first-launch")
        return detail

    def launch(self, package):
        resolved = self.adb("shell", "cmd", "package", "resolve-activity", "--brief", "-a",
                            "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", package)
        matches = [line.strip() for line in resolved.splitlines()
                   if re.fullmatch(re.escape(package) + r"/[A-Za-z0-9_.$]+", line.strip())]
        if len(matches) != 1:
            raise SmokeFailure(f"Cannot resolve one installed launcher for {package}: {resolved}")
        result = self.adb("shell", "am", "start", "-W", "-n", matches[0], timeout=90)
        if "Error:" in result or "Status: timeout" in result:
            raise SmokeFailure(f"Launch failed: {result}")

    def select_ime(self):
        available = self.adb("shell", "ime", "list", "-a", "-s")
        if self.ime not in available.split():
            raise SmokeFailure(f"Manifest IME is not registered: {self.ime}")
        self.adb("shell", "ime", "enable", self.ime)
        self.adb("shell", "ime", "set", self.ime)
        current = self.adb("shell", "settings", "get", "secure", "default_input_method").strip()
        if current != self.ime:
            raise SmokeFailure(f"Selected IME differs: {current}")

    def onboarding(self):
        self.launch(self.package)
        self.find("first-run-wizard", (WIZARD_TITLE,), package=self.package, timeout=60)
        self.select_ime()
        _, finish = self.find("rime-preparation-and-onboarding-ready", ("开始使用",),
                              package=self.package, scroll="down", timeout=self.args.ready_timeout)
        self.touch(finish)
        self.snapshot("onboarding-finished")
        return {"completion_control": "开始使用", "ime": self.ime,
                "provisioning": "adb ime enable/set; actual first-run preparation and UI finish button"}

    def blank_editor(self):
        self.launch(self.host_package)
        # Fresh connections close stale panels/compositions; only fictional host text is cleared.
        for label in ("Text B", "Text A", "Clear"):
            self.tap("host-" + slug(label), (label,), package=self.host_package)
        self.assert_editor("")

    def assert_editor(self, expected):
        root, editor = self.find("host-editor-value", package=self.host_package,
                                 resource_id=f"{self.host_package}:id/editor_a")
        status = choose_node(root, package=self.host_package, resource_id=f"{self.host_package}:id/editor_status")
        actual = editor.get("text", "")
        # Native EditText accessibility may expose its hint when its value is empty.
        if not expected and actual == "Text A" and status is not None and "UTF-16 length=0" in status.get("text", ""):
            actual = ""
        if actual != expected:
            raise SmokeFailure(f"Host text mismatch: expected {expected!r}, observed {actual!r}")
        length = len(expected.encode("utf-16-le")) // 2
        if status is None or f"UTF-16 length={length} |" not in status.get("text", ""):
            raise SmokeFailure("Native editor length status did not corroborate the text")

    def language(self, choice):
        self.tap("language-menu", ("语言切换",), hold=True)
        self.tap("choose-" + ("us" if "美国" in choice else "zh"), ("选择" + choice,))
        # Reopen to verify actual selected semantics, not just a successful tap.
        self.tap("verify-language-menu", ("语言切换",), hold=True)
        _, selected = self.find("selected-language", ("选择" + choice,), package=self.package)
        if selected.get("selected") != "true":
            raise SmokeFailure(f"Language row is not selected: {choice}")
        self.touch(selected)
        self.snapshot("language-menu-closed")

    def type_keys(self, word):
        for char in word:
            root = self.snapshot("soft-key-" + char)
            self.touch(qwerty_key(root, self.package, char))

    def chinese(self):
        self.blank_editor()
        self.language("中文")
        self.type_keys("nihao")
        self.tap("commit-nihao-candidate", ("你好",))
        self.assert_editor("你好")
        return {"soft_keys": "nihao", "candidate_tapped": "你好", "host_text": "你好"}

    def english(self):
        self.blank_editor()
        self.language("英文(美国)")
        self.type_keys("color")
        # A real space key ends the composing word. Sentence capitalization is valid.
        self.tap("commit-us-word-space", ("空格",))
        root, editor = self.find("us-editor-value", package=self.host_package,
                                 resource_id=f"{self.host_package}:id/editor_a")
        actual = editor.get("text", "")
        if actual not in ("color ", "Color "):
            raise SmokeFailure(f"US keyboard did not commit the typed word and space: {actual!r}")
        self.assert_editor(actual)
        return {"language_selection": "英文(美国)", "soft_keys": "color + space", "host_text": actual,
                "scope": "US mode and committed English input; not a dictionary-accuracy benchmark"}

    def cabin(self):
        self.blank_editor()
        self.tap("expand-keyboard-menu", ("展开菜单",))
        self.tap("open-tool-cabin", ("工具舱",), scroll="down")
        self.find("tool-cabin-open", ("关闭工具舱", "Close tool cabin"), package=self.package)

    def close_cabin(self):
        self.tap("close-tool-cabin", ("关闭工具舱", "Close tool cabin"))

    def save_fixture(self):
        self.cabin()
        self.tap("template-mode", ("动态模板", "Templates"))
        self.tap("csharp-preset", ("C#",))
        self.expect_text("csharp-template-source", CS_TEMPLATE)
        self.tap("save-template", ("保存模板原文", "Save template"), scroll="down")
        self.find("template-saved-confirmation", SAVED, package=self.package, scroll="down")
        self.close_cabin()
        return {"explicitly_saved_template_source": CS_TEMPLATE}

    def upgrade(self, *, evidence_name="upgraded-product-launch"):
        version = self.install(self.new)
        self.launch(self.package)
        root = self.snapshot(evidence_name)
        if not any(node.get("package") == self.package for node in root.iter("node")):
            raise SmokeFailure("Upgraded product activity has no accessible UI")
        if any(WIZARD_TITLE in labels(node) for node in root.iter("node")):
            raise SmokeFailure("Completed setup was reset to the first-run wizard after upgrade")
        selected = self.adb("shell", "settings", "get", "secure", "default_input_method").strip()
        if selected != self.ime:
            raise SmokeFailure(f"Default IME was not retained after package replacement: {selected}")
        return {"installed": version, "setup_wizard_reappeared": False, "selected_ime": selected,
                "installation": "adb install --streaming --no-incremental -r; no uninstall or clear-data"}

    def same_candidate_reinstall(self):
        self.installed_version(self.new)
        before = self.package_state("same-candidate-before-reinstall")
        result = self.upgrade(evidence_name="same-candidate-reinstalled-launch")
        after = self.package_state("same-candidate-after-reinstall")
        self.require_same_installation(before, after)
        return {**result, "replacement_kind": "same-version-same-APK-reinstall",
                "candidate_sha256": self.new["sha256"], "before": before, "after": after,
                "old_user_data_migration_tested": False}

    def restore_fixture(self, *, evidence_prefix="upgraded"):
        self.cabin()
        self.tap(evidence_prefix + "-template-mode", ("动态模板", "Templates"))
        self.tap("different-lua-preset", ("Lua",))
        self.expect_text("lua-source-before-load", LUA_TEMPLATE)
        self.tap("load-saved-template", ("我的模板", "My template"), scroll="down")
        self.expect_text("persisted-csharp-source", CS_TEMPLATE, scroll="up")
        self.close_cabin()
        return {"different_preset_seen": LUA_TEMPLATE, "loaded_saved_source": CS_TEMPLATE,
                "scope": "User-visible SharedPreferences template survives real APK replacement"}

    def units(self):
        self.cabin()
        self.tap("calculate-mode", ("随手算", "Calculate"))
        self.expect_text("unit-input-source", "2.5 MiB → B")
        self.tap("unit-preview", ("预览", "Preview"))
        self.expect_text("unit-preview-result", "2621440 B", scroll="down")
        self.assert_editor("")
        self.tap("insert-unit-result", ("插入结果", "Insert result"))
        self.assert_editor("2621440 B")
        return {"source": "2.5 MiB → B", "preview": "2621440 B", "host_before_insert": "", "host_after_insert": "2621440 B"}

    def run(self):
        if self.mode != "legacy-upgrade":
            return self.run_candidate()
        env = self.case("environment-and-apk-identities", self.environment)
        offline = self.case("disable-network-before-product", self.network, requires=env)
        installed = self.case("fresh-baseline-streaming-install", self.baseline_install, requires=offline)
        ready = self.case("first-run-rime-and-ime-setup", self.onboarding, requires=installed)
        self.case("baseline-chinese-commit", self.chinese, requires=ready)
        self.case("baseline-us-english-commit", self.english, requires=ready)
        saved = self.case("baseline-save-template-fixture", self.save_fixture, requires=ready)
        # Input/fixture failures do not prevent observing the actual upgrade and new input.
        upgraded = self.case("replace-apk-and-retain-setup", self.upgrade, requires=ready)
        self.case("upgraded-load-template-fixture", self.restore_fixture, requires=upgraded and saved)
        self.case("upgraded-chinese-commit", self.chinese, requires=upgraded and ready)
        self.case("upgraded-us-english-commit", self.english, requires=upgraded and ready)
        self.case("tool-cabin-units-preview-insert", self.units, requires=upgraded and ready, required=False)
        self.report["cases"].append({
            "name": "private-clipboard-close-and-process-restart", "required": False, "status": "not_run",
            "reason": "Deferred until core accessibility nodes are observed; no private clipboard or process-restart pass is inferred from unit tests.",
            "evidence": [],
        })
        failed = [case for case in self.report["cases"] if case["required"] and case["status"] != "passed"]
        self.report.update(status="failed" if failed else "core_passed", finished_utc=utc())
        self.report["counts"] = {status: sum(case["status"] == status for case in self.report["cases"])
                                 for status in ("passed", "failed", "blocked", "not_run")}
        self.save()
        print(json.dumps({"status": self.report["status"], "counts": self.report["counts"],
                          "report": str(self.output / "result.json")}, ensure_ascii=False), flush=True)
        return 1 if failed else 0

    def run_candidate(self):
        env = self.case("candidate-environment-and-locked-identities", self.environment)
        offline = self.case("disable-network-before-product", self.network, requires=env)
        install_name = "fresh-candidate-install" if self.mode == "fresh-candidate" else "replace-installed-uninitialized-1-1-1"
        installed = self.case(install_name, self.candidate_install, requires=offline)
        ready = self.case("candidate-first-launch-rime-and-ime-setup", self.onboarding, requires=installed)
        self.case("candidate-chinese-commit", self.chinese, requires=ready)
        self.case("candidate-us-english-commit", self.english, requires=ready)
        self.case("candidate-tool-cabin-units-preview-insert", self.units, requires=ready)
        if self.mode == "fresh-candidate":
            saved = self.case("candidate-save-new-template-fixture", self.save_fixture, requires=ready)
            reinstalled = self.case("same-candidate-reinstall-retains-setup", self.same_candidate_reinstall, requires=ready)
            retained = self.case("same-candidate-load-new-template-fixture",
                lambda: self.restore_fixture(evidence_prefix="same-candidate"), requires=reinstalled and saved)
            self.report["same_candidate_data_retention_tested"] = self.report["cases"][-1]["status"] in ("passed", "failed")
            self.report["same_candidate_data_retention_passed"] = retained
            self.case("reinstalled-candidate-chinese-commit", self.chinese, requires=reinstalled)
            self.case("reinstalled-candidate-us-english-commit", self.english, requires=reinstalled)
        self.report["cases"].append({"name": "private-clipboard-close-and-process-restart", "required": False,
            "status": "not_run", "reason": "The separate clipboard driver must pass on this installed candidate; core success does not imply clipboard acceptance", "evidence": []})
        failed = [case for case in self.report["cases"] if case["required"] and case["status"] != "passed"]
        self.report.update(status="failed" if failed else "core_passed", finished_utc=utc())
        self.report["counts"] = {status: sum(case["status"] == status for case in self.report["cases"])
                                 for status in ("passed", "failed", "blocked", "not_run")}
        self.save()
        print(json.dumps({"mode": self.mode, "status": self.report["status"], "counts": self.report["counts"],
                          "old_user_data_migration_tested": False, "report": str(self.output / "result.json")}, ensure_ascii=False), flush=True)
        return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=RELEASES.MODES, default="legacy-upgrade")
    parser.add_argument("--candidate-lock", type=Path, help="Required explicit signed-candidate identity for either new mode")
    parser.add_argument("--old-apk", type=Path)
    parser.add_argument("--new-apk", type=Path, required=True)
    parser.add_argument("--host-apk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New evidence directory; existing result.json is never overwritten")
    parser.add_argument("--serial", help="emulator-* only; defaults to ANDROID_SERIAL or emulator-5554")
    parser.add_argument("--ready-timeout", type=int, default=300, help="Maximum seconds to await real first-run Rime preparation")
    args = parser.parse_args()
    if args.mode != "legacy-upgrade" and args.candidate_lock is None:
        parser.error("--candidate-lock is required for " + args.mode + "; no latest APK is selected")
    if args.mode == "legacy-upgrade" and args.candidate_lock is not None:
        parser.error("--candidate-lock is not used by the unchanged legacy-upgrade inputs")
    if args.mode in ("legacy-upgrade", "replace-uninitialized") and args.old_apk is None:
        parser.error("--old-apk is required for " + args.mode)
    if args.mode == "fresh-candidate" and args.old_apk is not None:
        parser.error("fresh-candidate has no old APK; use a fresh guest and omit --old-apk")
    if args.ready_timeout < 30:
        parser.error("--ready-timeout must be at least 30 seconds")
    try:
        return Smoke(args).run()
    except (SmokeFailure, OSError) as error:
        print(f"Device smoke could not start: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
