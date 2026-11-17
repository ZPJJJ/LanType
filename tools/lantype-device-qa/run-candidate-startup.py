#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install and observe only the unchanged 1.1.1 candidate on a fresh API 35 guest.

This is an installation/startup check, not input, upgrade, or clipboard acceptance.
Never clears app data, uninstalls a package, substitutes an APK, or enables the IME.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import time


SPEC = importlib.util.spec_from_file_location(
    "lantype_core_smoke", Path(__file__).with_name("run-device-smoke.py"))
CORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CORE)

PACKAGE = "app.lantype.keyboard"
CANDIDATE_SHA256 = "b841c42366df2db7ef16736ee93a65723e6495aae91dab2e27093db06a40e497"
CANDIDATE_BYTES = 179987242
CERT_SHA256 = "c03b15a19d2ed8899fee6b71f7be09ea5b54c7db9895d7d87b20a9759d8e090b"


class CandidateStartup(CORE.Smoke):
    def __init__(self, args):
        self.startup_deadline = None
        super().__init__(args)
        self.report.update(
            mode="candidate-startup",
            scope="Fresh install and first-launch observation of the exact signed 1.1.1 APK only.",
            startup_timeout_seconds=args.startup_timeout,
            not_covered=[
                "Chinese/English input, Rime deployment completion, or IME enable/select",
                "Upgrade or retained data from an older product version",
                "Tool-cabin, clipboard privacy, or product process-restart flows",
                "Physical ARM64, 16 KiB pages, performance, or battery acceptance",
            ],
        )
        self.save()

    def command(self, argv, **kwargs):
        if self.startup_deadline is not None:
            remaining = self.startup_deadline - time.monotonic()
            if remaining <= 0:
                raise CORE.SmokeFailure("Candidate startup observation deadline reached")
            kwargs["timeout"] = min(kwargs.get("timeout", 60), remaining)
        return super().command(argv, **kwargs)

    def environment(self):
        # The shared environment() requires an increasing old/new APK pair.
        # Repeat only its read-only guest checks; candidate mode has no baseline.
        devices = self.command([self.adb_path, "devices", "-l"])
        ready = [line.split()[0] for line in devices.splitlines()[1:]
                 if len(line.split()) > 1 and line.split()[1] == "device"]
        if self.serial not in ready:
            raise CORE.SmokeFailure("The explicitly selected emulator is not ready")
        props = {name: self.adb("shell", "getprop", name).strip() for name in (
            "ro.build.version.sdk", "ro.build.version.release", "ro.build.fingerprint",
            "ro.product.model", "ro.product.cpu.abilist", "ro.product.cpu.abilist64",
            "ro.dalvik.vm.native.bridge", "ro.enable.native.bridge.exec",
            "sys.boot_completed", "ro.kernel.qemu")}
        user = self.adb("shell", "am", "get-current-user").strip()
        users = self.adb("shell", "dumpsys", "user")
        (self.output / "preflight-users.txt").write_text(users)
        result = {"serial": self.serial, "properties": props, "current_user": user,
                  "page_size": self.adb("shell", "getconf", "PAGESIZE", check=False).strip(),
                  "users_evidence": "preflight-users.txt"}
        self.report["environment"] = result
        user_zero = re.search(r"UserInfo\{0:.*?(?=\n\s*UserInfo\{|\Z)", users, re.S)
        if (props["ro.build.version.sdk"] != "35" or props["sys.boot_completed"] != "1"
                or props["ro.kernel.qemu"] != "1" or user != "0"
                or not user_zero or "RUNNING_UNLOCKED" not in user_zero[0]):
            raise CORE.SmokeFailure("Candidate mode requires a booted API 35 emulator with unlocked user 0")
        if ("arm64-v8a" not in props["ro.product.cpu.abilist"].split(",")
                or props["ro.dalvik.vm.native.bridge"] in ("", "0")
                or props["ro.enable.native.bridge.exec"] != "1"):
            raise CORE.SmokeFailure("Actual guest ARM64/native-bridge gates did not pass")

        candidate = self.apk(self.args.candidate_apk, ime=True)
        if (candidate["package"] != PACKAGE or candidate["version_code"] != 3
                or candidate["version_name"] != "1.1.1"
                or candidate["sha256"] != CANDIDATE_SHA256
                or candidate["bytes"] != CANDIDATE_BYTES):
            raise CORE.SmokeFailure("Candidate differs from the fixed released 1.1.1 APK")
        signer = shutil.which("apksigner") or str(Path(self.aapt).with_name("apksigner"))
        signature = self.command([signer, "verify", "--verbose", "--print-certs", candidate["path"]])
        (self.output / "candidate-signature.txt").write_text(signature)
        certificates = re.findall(
            r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})\s*$", signature, re.M)
        if [value.lower() for value in certificates] != [CERT_SHA256]:
            raise CORE.SmokeFailure("Candidate signer does not match the established release certificate")
        candidate.update(certificate_sha256=CERT_SHA256, signature_evidence="candidate-signature.txt")
        host = self.apk(self.args.host_apk)
        if host["package"] != "app.lantype.testhost":
            raise CORE.SmokeFailure("Expected the separate synthetic editor host")
        self.candidate, self.host = candidate, host
        self.package, self.host_package, self.ime = PACKAGE, host["package"], candidate["ime"]
        self.report["apks"] = {"candidate": candidate, "host": host}
        self.device_authorized = True
        return result

    def fresh_install(self):
        for info in (self.candidate, self.host):
            if "package:" in self.adb("shell", "pm", "path", info["package"], check=False):
                raise CORE.SmokeFailure("Fresh guest required; an existing package will not be cleared or replaced")
        installed = {}
        for role, info in (("candidate", self.candidate), ("host", self.host)):
            # Omit -r: even a package installed after the freshness check must
            # not be overwritten. The exact candidate is the first product APK.
            answer = self.adb("install", "--streaming", "--no-incremental", info["path"], timeout=180)
            if "Success" not in answer:
                raise CORE.SmokeFailure(f"Fresh {role} install did not report success: {answer}")
            installed[role] = self.installed_version(info)
        self.snapshot("candidate-and-host-installed")
        return installed

    def startup_diagnostics(self):
        evidence = {}
        # Fixed read-only paths on the already-authorized disposable guest.
        # Cap records and each sysfs value; absent cache directories are evidence.
        cache_topology = (
            "count=0; "
            "for base in /sys/devices/system/cpu/cpu[0-9]*/cache/index*; do "
            "[ -d \"$base\" ] || continue; "
            "for field in level type size shared_cpu_list; do "
            "if [ \"$count\" -ge 256 ]; then printf 'record limit reached\\n'; exit 0; fi; "
            "file=\"$base/$field\"; printf '%s: ' \"$file\"; "
            "if [ -r \"$file\" ]; then head -c 4096 \"$file\"; else printf 'unreadable\\n'; fi; "
            "count=$((count + 1)); done; done; "
            "printf 'cache fields observed: %s\\n' \"$count\""
        )
        for name, argv in (
            ("cpuinfo", ("shell", "head", "-c", "262144", "/proc/cpuinfo")),
            ("cpu-cache-topology", ("shell", cache_topology)),
            ("native-dropbox", ("shell", "dumpsys", "dropbox", "--print", "data_app_native_crash")),
            ("native-tombstones", ("shell", "dumpsys", "dropbox", "--print", "SYSTEM_TOMBSTONE")),
            ("exit-info", ("shell", "dumpsys", "activity", "exit-info", self.package)),
            ("pid", ("shell", "pidof", self.package)),
        ):
            filename = f"candidate-{name}.txt"
            try:
                text = self.adb(*argv, timeout=15, check=False)
                (self.output / filename).write_text(text)
                evidence[name] = {"file": filename, "captured": True}
            except (CORE.SmokeFailure, OSError) as error:
                evidence[name] = {"captured": False, "error": str(error)}
        self.report["startup_diagnostics"] = evidence
        self.save()

    def startup(self):
        self.startup_deadline = time.monotonic() + self.args.startup_timeout
        try:
            self.launch(self.package)
            self.find("candidate-first-run-wizard", (CORE.WIZARD_TITLE,),
                      package=self.package, timeout=self.args.startup_timeout)
            pids = self.adb("shell", "pidof", self.package, check=False).strip().split()
            if len(pids) != 1 or not pids[0].isdigit():
                raise CORE.SmokeFailure(f"Visible candidate has no unique live main PID: {pids}")
            self.snapshot("candidate-first-run-wizard-visible")
        finally:
            # Bound launch/UI observation to 120 seconds; evidence collection
            # has separate short per-command limits and also runs after failure.
            self.startup_deadline = None
            self.startup_diagnostics()
        diagnostics = self.report["startup_diagnostics"]
        if not diagnostics["exit-info"]["captured"] or not diagnostics["pid"]["captured"]:
            raise CORE.SmokeFailure("Could not retain final PID and exit-info evidence")
        exit_info = (self.output / diagnostics["exit-info"]["file"]).read_text()
        if "ACTIVITY MANAGER PROCESS EXIT INFO" not in exit_info:
            raise CORE.SmokeFailure("System exit-info response was not readable")
        if re.search(r"reason=(?:4|5|6)\s*\(", exit_info):
            raise CORE.SmokeFailure("System exit-info records a Java/native crash or ANR during first launch")
        final_pids = (self.output / diagnostics["pid"]["file"]).read_text().strip().split()
        if final_pids != pids:
            raise CORE.SmokeFailure("Candidate main PID disappeared or changed during startup capture")
        return {"wizard_title": CORE.WIZARD_TITLE, "main_pid": int(pids[0]),
                "scope": "Wizard visibility plus a live PID and no recorded crash/ANR; no onboarding completion or input claim"}

    def run(self):
        env = self.case("candidate-environment-and-signed-identity", self.environment)
        offline = self.case("disable-network-before-candidate", self.network, requires=env)
        installed = self.case("fresh-candidate-and-host-install", self.fresh_install, requires=offline)
        self.case("candidate-first-launch", self.startup, requires=installed)
        failed = any(case["status"] != "passed" for case in self.report["cases"])
        self.report.update(status="failed" if failed else "startup_passed", finished_utc=CORE.utc())
        self.report["counts"] = {status: sum(case["status"] == status for case in self.report["cases"])
                                 for status in ("passed", "failed", "blocked", "not_run")}
        self.save()
        print(json.dumps({"mode": "candidate-startup", "status": self.report["status"],
                          "counts": self.report["counts"], "report": str(self.output / "result.json")}), flush=True)
        return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-apk", type=Path, required=True)
    parser.add_argument("--host-apk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--serial", help="emulator-* only; defaults to ANDROID_SERIAL or emulator-5554")
    parser.add_argument("--startup-timeout", type=int, default=120)
    args = parser.parse_args()
    if not 30 <= args.startup_timeout <= 120:
        parser.error("--startup-timeout must be between 30 and 120 seconds")
    try:
        return CandidateStartup(args).run()
    except (CORE.SmokeFailure, OSError) as error:
        print(f"Candidate startup check could not start: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
