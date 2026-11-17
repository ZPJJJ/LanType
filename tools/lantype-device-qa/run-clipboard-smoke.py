#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded, optional clipboard extension after a successful real APK core smoke.

Requires the QA host's explicit Inspect button. Installs/clears nothing, never
writes the clipboard through adb, and never upgrades missing evidence to a pass.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace

SPEC = importlib.util.spec_from_file_location("lantype_core_smoke", Path(__file__).with_name("run-device-smoke.py"))
CORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CORE)
CS = CORE.CS_TEMPLATE
LUA = CORE.LUA_TEMPLATE
NORMAL_BEFORE = "fixture {{date}}"
NORMAL_AFTER = "Contact demo@example.test; phone 13800138000"


class EvidenceBlocked(CORE.SmokeFailure):
    pass


def fixture_identity(metadata, expected, private):
    if metadata.get("error"):
        raise EvidenceBlocked(f"QA host could not inspect this synthetic fixture: {metadata['error']}")
    expected_hash = hashlib.sha256(expected.encode("utf-8")).hexdigest()
    if metadata.get("text_sha256") != expected_hash or metadata.get("utf16_length") != len(expected.encode("utf-16-le")) // 2:
        raise AssertionError("The explicitly copied synthetic text differs from the intended selection")
    if metadata.get("tool_cabin_private") is not private or metadata.get("sensitive") is not private:
        raise AssertionError("Clipboard privacy extras do not match the copy's source")
    if private and metadata.get("label") != "LanType tool cabin":
        raise AssertionError("Private copy did not retain its tool-cabin label")
    if metadata.get("item_count") != 1 or "text/plain" not in metadata.get("mime_types", []):
        raise EvidenceBlocked("Expected one inspectable plain-text fixture")


def same_recent_clip(before, after):
    fields = ("timestamp_ms", "text_sha256", "utf16_length", "label", "mime_types",
              "item_count", "tool_cabin_private", "sensitive", "fixture")
    if any(before.get(field) != after.get(field) for field in fields):
        raise AssertionError("System clipboard identity/metadata changed across the process restart")
    age = after["observed_at_epoch_ms"] - after["timestamp_ms"]
    if not 0 <= age < 30_000:
        raise EvidenceBlocked(f"blocked_timing: actual guest clipboard age is {age} ms, outside [0, 30000)")
    wall = after["observed_at_epoch_ms"] - before["observed_at_epoch_ms"]
    elapsed = after["observed_at_elapsed_ms"] - before["observed_at_elapsed_ms"]
    if elapsed < 0 or abs(wall - elapsed) > 2000:
        raise EvidenceBlocked("Guest clock changed during the same-clip observation")
    return age


class ClipboardSmoke(CORE.Smoke):
    def __init__(self, args, core_report):
        self.deadline = time.monotonic() + args.deadline_seconds
        self.core_report_path = args.core_report.resolve()
        self.core_report = core_report
        apks = core_report["apks"]
        mode = core_report.get("mode", "legacy-upgrade")
        if mode not in CORE.RELEASES.MODES:
            raise EvidenceBlocked("Clipboard extension requires a recognized functional core mode")
        expected_roles = {"new", "host"} if mode == "fresh-candidate" else {"old", "new", "host"}
        if set(apks) != expected_roles:
            raise EvidenceBlocked("Core APK roles do not match its installation mode")
        lock_path = None
        if mode != "legacy-upgrade":
            lock = core_report.get("candidate_lock", {})
            lock_path = Path(lock.get("path", ""))
            if not lock_path.is_file() or CORE.RELEASES.file_sha256(lock_path) != lock.get("sha256"):
                raise EvidenceBlocked("The explicit candidate lock differs from the passed core receipt")
        serial = args.serial or os.environ.get("ANDROID_SERIAL") or "emulator-5554"
        if serial != core_report.get("environment", {}).get("serial"):
            raise EvidenceBlocked("Clipboard extension must use the exact core-smoke emulator")
        super().__init__(SimpleNamespace(output=args.output, serial=serial, mode=mode, candidate_lock=lock_path,
            old_apk=Path(apks["old"]["path"]) if "old" in apks else None,
            new_apk=Path(apks["new"]["path"]), host_apk=Path(apks["host"]["path"]), ready_timeout=30))
        self.report.update(scope="Explicit synthetic clipboard copies on the unchanged installed release; optional extension, separate from core results.",
            core_report=str(self.core_report_path), core_mode=mode, deadline_seconds=args.deadline_seconds,
            clipboard_observations=[], not_covered=["Cut (not run)", "Physical ARM64/16 KiB/performance acceptance", "Arbitrary private database enumeration"])
        self.save()

    def command(self, argv, **kwargs):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise EvidenceBlocked("Total clipboard extension deadline reached")
        kwargs["timeout"] = min(kwargs.get("timeout", 60), remaining)
        try:
            return super().command(argv, **kwargs)
        except CORE.SmokeFailure as error:
            if "timed out" in str(error):
                raise EvidenceBlocked(str(error)) from error
            raise

    def find(self, *args, **kwargs):
        kwargs["timeout"] = min(kwargs.get("timeout", 8), 8)
        try:
            return super().find(*args, **kwargs)
        except CORE.SmokeFailure as error:
            raise EvidenceBlocked(str(error)) from error

    def case(self, name, action, **kwargs):
        result = super().case(name, action, **kwargs)
        record = self.report["cases"][-1]
        if record.get("reason", "").startswith(("EvidenceBlocked:", "SmokeFailure:")):
            record["status"] = "blocked"
            self.save()
        return result

    def host_tap(self, label):
        root = self.snapshot("host-" + CORE.slug(label))
        nodes = [node for node in root.iter("node")
                 if node.get("package") == self.host_package and node.get("class") == "android.widget.Button"
                 and label in CORE.labels(node) and CORE.bounds(node) and node.get("enabled") != "false"]
        unique = {CORE.bounds(node): node for node in nodes}
        if len(unique) != 1:
            raise EvidenceBlocked(f"Need one visible native QA host button: {label}")
        self.touch(next(iter(unique.values())))

    def observe(self, name, expected, private):
        self.host_tap("Inspect")
        _, message = self.find(name + "-metadata", package=self.host_package, resource_id="android:id/message")
        try:
            metadata = json.loads(message.get("text", ""))
        except (ValueError, TypeError) as error:
            raise EvidenceBlocked("Inspect dialog did not expose complete JSON metadata") from error
        self.report["clipboard_observations"].append({"name": name, **metadata})
        self.save()
        self.tap("dismiss-inspection", ("Done",), package=self.host_package)
        fixture_identity(metadata, expected, private)
        return metadata

    def pid(self, package):
        value = self.adb("shell", "pidof", package, check=False).strip().split()
        if len(value) != 1 or not value[0].isdigit():
            raise EvidenceBlocked(f"Cannot identify one live process for {package}: {value}")
        return int(value[0])

    def package_state(self, name):
        dump = self.adb("shell", "dumpsys", "package", self.package)
        (self.output / (name + "-package.txt")).write_text(dump)
        fields = {}
        for field in ("userId", "dataDir", "ceDataInode", "firstInstallTime", "lastUpdateTime", "versionCode", "versionName"):
            match = re.search(r"\b" + field + r"=([^\n]+)", dump)
            if match:
                fields[field] = match[1].strip()
        return fields

    def ready(self):
        result = super().environment()
        if set(self.report["apks"]) != set(self.core_report["apks"]):
            raise EvidenceBlocked("APK roles changed after the core smoke")
        for key in self.core_report["apks"]:
            current, expected = self.report["apks"][key], self.core_report["apks"][key]
            fields = ("sha256", "bytes", "package", "version_code", "version_name", "ime", "certificate_sha256")
            if any(current.get(field) != expected.get(field) for field in fields):
                raise EvidenceBlocked("An APK identity differs from the passed core receipt")
        self.installed_version(self.new)
        self.installed_version(self.host)
        current = self.adb("shell", "settings", "get", "secure", "default_input_method").strip()
        if current != self.ime:
            raise EvidenceBlocked("Core's actual IME is no longer selected")
        radio = {key: self.adb("shell", "settings", "get", "global", key).strip()
                 for key in ("airplane_mode_on", "wifi_on", "mobile_data")}
        if radio != {"airplane_mode_on": "1", "wifi_on": "0", "mobile_data": "0"}:
            raise EvidenceBlocked("The core's offline radio configuration is no longer retained")
        self.install_state = self.package_state("before-extension")
        self.launch(self.host_package)
        self.host_tap("Text B")
        self.host_tap("Text A")
        self.host_tap("Clear")
        self.assert_editor("")
        # An unknown clip must not be inspected as a substitute for this explicit write.
        self.host_tap("Clipboard")
        metadata = self.observe("normal-before", NORMAL_BEFORE, False)
        self.read_log(self.pid(self.package), metadata, "NORMAL")
        self.board(NORMAL_BEFORE, forbidden=(NORMAL_AFTER, CS, LUA), baseline=True)
        return {"environment": result, "normal_baseline": metadata}

    def leave_board(self):
        # Standard Back on the known open board; no guessed coordinate/hidden command.
        self.adb("shell", "input", "keyevent", "KEYCODE_BACK")
        self.host_tap("Text B")
        self.host_tap("Text A")
        self.host_tap("Clear")
        self.assert_editor("")

    def board(self, expected, forbidden=(CS, LUA), baseline=False):
        root = self.snapshot("locate-clipboard-entry")
        entry = None
        for label in ("剪贴板", "打开剪贴板", "剪切板"):
            entry = CORE.choose_node(root, (label,), package=self.package)
            if entry is not None:
                break
        if entry is None:
            raise EvidenceBlocked("No actual clipboard entry is visible")
        self.touch(entry)
        self.tap("all-clipboard-category", ("全部",))
        root, tab = self.find("all-history-observation", ("全部",), package=self.package)
        if tab.get("selected") != "true":
            raise EvidenceBlocked("Cannot establish the selected All history category")
        texts = {node.get("text", "").strip() for node in root.iter("node") if node.get("package") == self.package}
        if expected not in texts:
            raise EvidenceBlocked("The normal positive control is not visible in All history")
        if any(value in text for value in forbidden for text in texts) or "••••••••" in texts:
            if baseline:
                raise EvidenceBlocked("History already contains later/private fixture content; no clean baseline is established")
            raise AssertionError("A forbidden private/unexpected sample or masked secret card is visible in history")
        if any("🔍" in text or "无痕模式开着" in text for text in texts):
            raise EvidenceBlocked("Search/manual incognito prevents an unambiguous normal-history control")
        return {"normal_visible": expected, "private_samples_visible": False,
                "scope": "Visible All history plus independently verified read classification; not private DB enumeration"}

    def private_copy(self, preset, expected):
        self.leave_board()
        self.cabin()
        self.tap("templates", ("动态模板", "Templates"))
        self.tap("private-preset-" + CORE.slug(preset), (preset,))
        self.expect_text("private-source", expected)
        self.tap("edit-private-source", ("编辑输入", "Edit input"))
        root = self.snapshot("private-native-editor")
        editors = [node for node in root.iter("node") if node.get("package") == self.package
                   and node.get("class") == "android.widget.EditText" and node.get("text") == expected
                   and node.get("focused") == "true" and CORE.bounds(node)]
        if len(editors) != 1:
            raise EvidenceBlocked("The intended cabin native EditText is not visibly focused")
        self.tap("internal-edit-toolbar", ("编辑",))
        self.tap("select-entire-private-source", ("全选",))
        self.tap("explicit-private-copy", ("复制",))
        root = self.snapshot("copy-keeps-draft")
        if not any(node.get("package") == self.package and node.get("class") == "android.widget.EditText"
                   and node.get("text") == expected for node in root.iter("node")):
            raise AssertionError("Copy did not preserve the cabin draft")
        self.tap("close-native-tool-cabin", ("关闭",))
        root = self.snapshot("cabin-closed")
        if any(node.get("package") == self.package and (node.get("class") == "android.widget.EditText"
               or CORE.labels(node).intersection(("工具舱", "Tool cabin", "关闭工具舱", "Close tool cabin")))
               for node in root.iter("node")):
            raise EvidenceBlocked("Cabin closure was not observed before clipboard inspection")
        self.assert_editor("")
        return self.observe("private-" + CORE.slug(preset), expected, True)

    def read_log(self, pid, metadata, privacy):
        log = self.adb("logcat", "-d", "--pid", str(pid), "-v", "epoch", "-s", "ClipboardManager:I", "*:S", timeout=8)
        name = f"clipboard-read-{pid}-{privacy.lower()}-{len(self.report['clipboard_observations'])}.txt"
        (self.output / name).write_text(log)
        # Require a read of this copy by this process, within the actual observed guest interval.
        matched = []
        for line in log.splitlines():
            stamp = re.match(r"\s*(\d+\.\d+)\s", line)
            if not stamp or "clip read:" not in line or f"privacy={privacy}" not in line or "empty=false" not in line:
                continue
            millis = int(float(stamp[1]) * 1000)
            if not metadata["timestamp_ms"] <= millis <= metadata["observed_at_epoch_ms"]:
                continue
            if f"t{metadata['utf16_length']}u0i0" not in line:
                continue
            if privacy == "PRIVATE" and ("label=LanType tool cabin" not in line or "sensitive=true" not in line):
                continue
            matched.append(line)
        if not matched:
            raise EvidenceBlocked(f"No actual {privacy} read trace for this clip in PID {pid}; absence in history alone is insufficient")
        return {"pid": pid, "trace": name, "matching_reads": len(matched)}

    def closed_private(self):
        before = self.private_copy("C#", CS)
        trace = self.read_log(self.pid(self.package), before, "PRIVATE")
        history = self.board(NORMAL_BEFORE)
        return {"clip": before, "read": trace, "history": history}

    def restarted_private(self):
        old_pid, server_pid = self.pid(self.package), self.pid("system_server")
        before = self.private_copy("Lua", LUA)
        # Nothing in this interval writes/replaces clipboard data, restarts Android or clears app data.
        self.adb("shell", "am", "force-stop", "--user", "0", self.package)
        stopped = self.adb("shell", "pidof", self.package, check=False).strip()
        if stopped:
            raise EvidenceBlocked(f"Old process termination was not directly observed: {stopped}")
        self.launch(self.package)
        self.launch(self.host_package)
        self.host_tap("Text A")
        new_pid = self.pid(self.package)
        if new_pid == old_pid or self.pid("system_server") != server_pid:
            raise EvidenceBlocked("Cannot prove only the product process was recreated")
        current = self.adb("shell", "settings", "get", "secure", "default_input_method").strip()
        if current != self.ime:
            raise EvidenceBlocked("Force-stop changed the selected IME; rebind behavior needs separate evidence")
        after = self.observe("same-private-after-restart", LUA, True)
        age = same_recent_clip(before, after)
        trace = self.read_log(new_pid, after, "PRIVATE")
        history = self.board(NORMAL_BEFORE)
        after_state = self.package_state("after-restart")
        if after_state != self.install_state:
            raise EvidenceBlocked("Public package identity changed across the extension")
        return {"old_pid": old_pid, "stopped_pidof": stopped, "new_pid": new_pid,
                "system_server_pid": server_pid, "clipboard_age_ms": age, "same_identity": True,
                "read": trace, "history": history, "retained_public_package_state": after_state}

    def normal_after(self):
        self.leave_board()
        self.host_tap("Mask sample")  # Existing host fills/selects a different synthetic value; does not copy.
        self.tap("normal-edit-toolbar", ("编辑",))
        self.tap("explicit-normal-copy", ("复制",))
        metadata = self.observe("normal-after-private", NORMAL_AFTER, False)
        trace = self.read_log(self.pid(self.package), metadata, "NORMAL")
        history = self.board(NORMAL_AFTER)
        return {"new_normal_clip": metadata, "read": trace, "history": history}

    def run(self):
        ready = self.case("normal-copy-baseline", self.ready)
        closed = self.case("private-copy-and-observed-close", self.closed_private, requires=ready)
        self.case("same-private-clip-new-process", self.restarted_private, requires=closed)
        # Try the normal recovery control even if the restart assertion lacked evidence.
        self.case("new-normal-copy-after-private", self.normal_after, requires=closed)
        self.report["cases"].append({"name": "private-cut", "required": False, "status": "not_run",
                                     "reason": "This bounded extension exercises copy only", "evidence": []})
        required = [case for case in self.report["cases"] if case.get("required", True)]
        status = "passed" if all(case["status"] == "passed" for case in required) else (
            "failed" if any(case["status"] == "failed" for case in required) else "blocked")
        self.report.update(status=status, finished_utc=CORE.utc())
        self.report["counts"] = {value: sum(case["status"] == value for case in self.report["cases"])
                                  for value in ("passed", "failed", "blocked", "not_run")}
        self.save()
        print(json.dumps({"status": status, "counts": self.report["counts"], "report": str(self.output / "result.json")}), flush=True)
        return 0 if status == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--serial")
    parser.add_argument("--deadline-seconds", type=int, default=270)
    args = parser.parse_args()
    if not 30 <= args.deadline_seconds <= 280:
        parser.error("--deadline-seconds must be 30..280 (hard budget below five minutes)")
    try:
        report = json.loads(args.core_report.read_text())
        required = [case for case in report.get("cases", []) if case.get("required")]
        if report.get("status") != "core_passed" or not required or not all(
                case.get("status") == "passed" for case in required):
            raise EvidenceBlocked("A completed successful core report is required")
        return ClipboardSmoke(args, report).run()
    except (OSError, KeyError, ValueError, CORE.SmokeFailure) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
