#!/usr/bin/env python3
"""Bounded environment wrapper for the existing signed-product QA scripts.

Only the temporary work slot, SDK preparation, allocation checkpoints and command
monitoring are shared with run-ort-api-qa.py. No positive API acceptance result is
reused: this file never invokes its identity, native build or probe execution.
Product acceptance comes exclusively from the unchanged functional drivers and
their actual reports. The shared work-slot names are local to one fresh hosted
job; setup refuses an existing slot. No product signing material is used here.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

SPEC = importlib.util.spec_from_file_location("lantype_shared_qa_environment", Path(__file__).with_name("run-ort-api-qa.py"))
SHARED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHARED)
PRODUCT = "app.lantype.keyboard"


def owned_emulator(driver):
    record = driver.root / "emulator.pid"
    if not record.is_file():
        return False
    pid = int(record.read_text().strip())
    command = Path("/proc") / str(pid) / "cmdline"
    if not command.exists():
        return False
    arguments = command.read_bytes().split(b"\0")
    SHARED.require(b"-avd" in arguments and SHARED.AVD.encode() in arguments and os.getpgid(pid) == pid,
                   "Refusing to use an unrelated emulator process")
    return True


def boot(driver):
    driver.budget("before-product-boot")
    driver.require_tools()
    SHARED.require(not (driver.root / "emulator.pid").exists(), "This job already started its one emulator")
    devices, _ = driver.run("adb-devices-before", [driver.sdk / "platform-tools/adb", "devices"])
    SHARED.require(not re.search(r"^" + re.escape(driver.serial) + r"\s", devices, re.M), "Emulator serial already belongs to another process")
    command = [str(driver.sdk / "emulator/emulator"), "-avd", SHARED.AVD, "-port", "5554",
               "-accel", "on", "-cores", "4", "-memory", "3072", "-gpu", "swiftshader",
               "-no-window", "-no-audio", "-no-boot-anim", "-no-snapshot", "-wipe-data", "-no-metrics"]
    with (driver.evidence / "emulator.stdout.txt").open("wb") as out, (driver.evidence / "emulator.stderr.txt").open("wb") as err:
        process = subprocess.Popen(command, stdout=out, stderr=err, env=driver.env,
                                   cwd=driver.root, start_new_session=True)
    (driver.root / "emulator.pid").write_text(str(process.pid) + "\n")
    SHARED.save(driver.evidence / "emulator-command.json", {"command": command, "pid": process.pid, "productQa": True})
    driver.adb("wait-for-device", "wait-for-device", timeout=120)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        SHARED.require(process.poll() is None, "Owned emulator exited before boot")
        state, _ = driver.adb("boot-completed", "shell", "getprop", "sys.boot_completed", timeout=10, check=False)
        users, _ = driver.adb("boot-users", "shell", "dumpsys", "user", timeout=10, check=False)
        if state.strip() == "1" and "RUNNING_UNLOCKED" in users:
            break
        time.sleep(3)
    else:
        raise ValueError("Guest did not reach boot complete with an unlocked user")
    properties, _ = driver.adb("guest-properties", "shell", "getprop")
    props = dict(re.findall(r"^\[([^]]+)\]: \[(.*)\]$", properties, re.M))
    abis = props.get("ro.product.cpu.abilist", "").split(",")
    SHARED.require(props.get("ro.build.version.sdk") == "35" and "x86_64" in abis and "arm64-v8a" in abis
                   and props.get("ro.dalvik.vm.native.bridge") not in (None, "", "0"), "Actual API 35 / ARM64 bridge gate failed")
    pre, _ = driver.adb("pre-product-logcat", "logcat", "-d", "-b", "all")
    SHARED.require(not re.search(r"WATCHDOG KILLING SYSTEM PROCESS|FATAL EXCEPTION IN SYSTEM PROCESS", pre), "Framework failed before product QA")
    # Keep the actual stream throughout product input/clipboard checks. It is
    # stopped by collect() using its owned PID, without truncating the evidence.
    with (driver.evidence / "product-live-logcat.txt").open("wb") as out:
        logcat = subprocess.Popen([str(driver.sdk / "platform-tools/adb"), "-s", driver.serial,
                                  "logcat", "-b", "all", "-v", "threadtime"],
                                 stdout=out, stderr=subprocess.STDOUT, env=driver.env,
                                 cwd=driver.root, start_new_session=True)
    (driver.root / "logcat.pid").write_text(str(logcat.pid) + "\n")
    driver.budget("after-product-boot")


def collect(driver):
    if not os.path.ismount(driver.root):
        return
    (driver.root / "evidence-reserve.bin").unlink(missing_ok=True)
    errors = []
    try:
        if owned_emulator(driver):
            commands = (
                ("final-product-logcat", ["logcat", "-d", "-b", "all"]),
                ("final-users", ["shell", "dumpsys", "user"]),
                ("product-package", ["shell", "dumpsys", "package", PRODUCT]),
                ("product-exit-info", ["shell", "dumpsys", "activity", "exit-info", PRODUCT]),
                ("product-input-method", ["shell", "dumpsys", "input_method"]),
                ("native-app-dropbox", ["shell", "dumpsys", "dropbox", "--print", "data_app_native_crash"]),
                ("native-tombstones", ["shell", "dumpsys", "dropbox", "--print", "SYSTEM_TOMBSTONE"]),
            )
            for label, command in commands:
                try:
                    driver.adb(label, *command, timeout=10, check=False)
                except (OSError, ValueError) as error:
                    errors.append(label + ": " + str(error))
            # Capture only the current UI; this does not interact with it or
            # change a functional driver's failed/blocked/pass assessment.
            remote = "/sdcard/lantype-product-final-ui.xml"
            for label, command, timeout, destination in (
                ("final-ui-dump", ["shell", "uiautomator", "dump", remote], 30, None),
                ("final-ui-copy", ["exec-out", "cat", remote], 10, driver.evidence / "final-ui.xml"),
                ("final-screen", ["exec-out", "screencap", "-p"], 10, driver.evidence / "final-screen.png"),
                ("remove-owned-ui-dump", ["shell", "rm", "-f", remote], 5, None),
            ):
                try:
                    driver.adb(label, *command, timeout=timeout, check=False, copy_stdout_to=destination)
                except (OSError, ValueError) as error:
                    errors.append(label + ": " + str(error))
    finally:
        # Never issue a broad kill or adb emu kill against just a serial name.
        for name, tokens in (("logcat", ["-s", driver.serial, "logcat"]), ("emulator", ["-avd", SHARED.AVD])):
            try:
                driver.stop_owned_process(name, tokens)
            except (OSError, ValueError) as error:
                errors.append("stop-" + name + ": " + str(error))
        SHARED.save(driver.receipts / "product-collection.json", {"diagnosticErrors": errors,
                    "productPackage": PRODUCT, "positiveApiAcceptanceReused": False})
    driver.budget("after-product-collection")
    SHARED.require(not any(item.startswith("stop-") for item in errors), "An owned process could not be stopped; volume must not be discarded")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("budget", "tools", "image", "boot", "execute", "collect"))
    parser.add_argument("--label", default="checkpoint")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    driver = None
    try:
        SHARED.require(re.fullmatch(r"[a-z0-9-]+", args.label), "Invalid environment step label")
        SHARED.require(1 <= args.timeout <= 900, "Command timeout must be 1..900 seconds")
        # The shared command monitor reserves space for failure diagnostics;
        # only its explicit collection stage may consume that reserve.
        os.environ["ORT_QA_STAGE"] = "collect" if args.stage == "collect" else "product-" + args.stage + "-" + args.label
        driver = SHARED.Driver()
        driver.env.update(ANDROID_HOME=str(driver.sdk), ANDROID_SDK_ROOT=str(driver.sdk),
            LD_LIBRARY_PATH=os.pathsep.join(filter(None, (str(driver.root / "host-libs/usr/lib/x86_64-linux-gnu"),
                                                         driver.env.get("LD_LIBRARY_PATH", "")))))
        driver.env["PATH"] = os.pathsep.join((str(driver.sdk / "platform-tools"),
            str(driver.sdk / "build-tools/36.0.0"), driver.env["PATH"]))
        SHARED.require(args.stage == "collect" or os.path.ismount(driver.root), "Bounded work volume must be mounted")
        if os.path.ismount(driver.root) and not (driver.evidence / "shared-environment-scope.json").exists():
            SHARED.save(driver.evidence / "shared-environment-scope.json", {
                "shared": ["fresh-job temporary work slot", "SDK overlay", "host loader dependencies", "allocation checkpoints", "command monitoring"],
                "helperSourceSha256": SHARED.digest(Path(__file__).with_name("run-ort-api-qa.py")),
                "positiveApiAcceptanceReused": False, "nativeProbeInvoked": False,
                "productAcceptanceSource": "Existing signed product functional and clipboard driver reports"})
        if args.stage == "execute":
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            SHARED.require(command, "An explicit product command is required")
            driver.budget("before-product-" + args.label)
            try:
                driver.run(args.label, command, timeout=args.timeout, cwd=SHARED.REPO)
            finally:
                driver.budget("after-product-" + args.label)
        elif args.stage == "budget":
            driver.budget(args.label)
        elif args.stage == "tools":
            driver.tools()
            aapt = driver.sdk / "build-tools/36.0.0/aapt"
            SHARED.require(aapt.is_file() and os.access(aapt, os.X_OK), "Product APK identity checks require SDK aapt")
        elif args.stage == "image":
            driver.image()
        elif args.stage == "boot":
            boot(driver)
        else:
            collect(driver)
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        failure = {"stage": args.stage, "label": args.label, "error": str(error),
                   "scope": "product-qa-environment", "positiveApiAcceptanceReused": False}
        if driver is not None:
            if os.path.ismount(driver.root):
                failure["volumeAfterFailure"] = driver.volume_usage()
                (driver.root / "evidence-reserve.bin").unlink(missing_ok=True)
            SHARED.save(driver.receipts / ("product-environment-failure-" + args.stage + "-" + args.label + ".json"), failure)
        print(json.dumps(failure), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
