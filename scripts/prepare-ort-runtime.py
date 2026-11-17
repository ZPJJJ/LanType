#!/usr/bin/env python3
"""Prepare or verify the pinned ORT Android runtime, without executing native code.

Locks are explicit, read-only inputs. Candidate locks allow preparation/content
comparison; accepted locks additionally pin both AARs and the copied ELF. Only
an accepted lock can verify a final APK or a source-build linker input. Acceptance
evidence hashes are provenance supplied by the lock's author, not device tests
performed by this program. See --help for the stable paths and command options.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import struct
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "vendor/ort-runtime"
BASELINE = ROOT / "docs/licensing/ort-shipped-abi.json"
BASELINE_SHA256 = "e0b561300641a4a966f658d5376153d48e9a8a1a6f8d99cf1f6bec49e6c0cc62"
OLD_APK_SHA256 = "b841c42366df2db7ef16736ee93a65723e6495aae91dab2e27093db06a40e497"
OLD_LIBRARY_SHA256 = "f826d8efb03adf0a84f10e7ba408f9d4cd11b0a2ccd8d08aeb0f7451fb50cacc"
ORIGINAL_AAR = {"bytes": 45634470,
                "sha256": "f351a0638696f54b35184290dbc001d66daae17281ad0b548d2c70347d53b8a9"}
MEMBER = "jni/arm64-v8a/libonnxruntime.so"
BRIDGE = "jni/arm64-v8a/libonnxruntime4j_jni.so"
REQUIRED_MEMBERS = {MEMBER, BRIDGE, "classes.jar", "AndroidManifest.xml"}
OUTPUTS = {
    "fullAar": "onnxruntime-android-1.28.0-lantype-r1.aar",
    "companionAar": "onnxruntime-android-1.28.0-lantype-r1-cmake.aar",
    "library": "arm64-v8a/libonnxruntime.so",
}
DATE = (1980, 1, 1, 0, 0, 0)
CHUNK = 1024 * 1024
GIB = 1024 ** 3


class RuntimePackageError(ValueError):
    """An invalid input or a failed content gate."""


def require(condition, message):
    if not condition:
        raise RuntimePackageError(message)


def stream_identity(stream, destinations=()):
    digest, size = hashlib.sha256(), 0
    for chunk in iter(lambda: stream.read(CHUNK), b""):
        digest.update(chunk)
        size += len(chunk)
        for destination in destinations:
            destination.write(chunk)
    return {"bytes": size, "sha256": digest.hexdigest()}


def file_identity(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), f"Not a regular file: {path}")
    with path.open("rb") as stream:
        return stream_identity(stream)


def identity(value, label):
    require(isinstance(value, dict), f"Missing {label} identity")
    size, digest = value.get("bytes"), value.get("sha256")
    require(type(size) is int and size >= 0, f"Invalid {label} byte count")
    require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest),
            f"Invalid {label} SHA-256")
    return {"bytes": size, "sha256": digest}


def match(actual, expected, label):
    require(actual == identity(expected, label), f"Content mismatch: {label}")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), f"Not a regular JSON file: {path}")
    require(path.stat().st_size <= CHUNK, f"JSON file too large: {path}")
    data = path.read_bytes()
    return json.loads(data, object_pairs_hook=unique_object), hashlib.sha256(data).hexdigest()


def load_lock(path, accepted):
    lock, digest = read_json(path)
    require(isinstance(lock, dict) and type(lock.get("schemaVersion")) is int
            and lock["schemaVersion"] == 1 and lock.get("kind") == "lantype-ort-runtime-lock",
            "Unsupported ORT runtime lock schema")
    require(lock.get("status") == ("accepted" if accepted else "candidate"),
            "Lock status does not match the explicit lock option")
    require(lock.get("ortVersion") == "1.28.0" and lock.get("abi") == "arm64-v8a",
            "The runtime lock must describe ORT 1.28.0 / arm64-v8a")
    match(identity(lock.get("originalAar"), "originalAar"), ORIGINAL_AAR, "official AAR pin")
    library = identity(lock.get("library"), "library")
    require(64 <= library["bytes"] <= 256 * CHUNK, "Replacement ELF size is outside the supported range")
    require(library["sha256"] != OLD_LIBRARY_SHA256, "Replacement is still the unchanged shipped ORT library")
    if accepted or "outputs" in lock:
        outputs = lock.get("outputs")
        require(isinstance(outputs, dict) and set(outputs) == set(OUTPUTS),
                "Lock outputs must pin fullAar, companionAar and library")
        for name, value in outputs.items():
            identity(value, name)
        match(identity(outputs["library"], "outputs.library"), library, "library output pin")
    if accepted:
        evidence = lock.get("acceptanceEvidence")
        require(isinstance(evidence, dict), "Accepted lock requires acceptanceEvidence references")
        for name in ("staticAbiReceiptSha256", "androidApiReceiptSha256"):
            value = evidence.get(name)
            require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
                    f"Missing accepted evidence hash: {name}")
    return lock, digest


def check_library(path, expected):
    actual = file_identity(path)
    match(actual, expected, "replacement ELF")
    with Path(path).open("rb") as stream:
        header = stream.read(64)
    require(len(header) == 64 and header[:7] == b"\x7fELF\x02\x01\x01",
            "Expected an ELF64 little-endian library")
    require(struct.unpack_from("<HHI", header, 16) == (3, 183, 1),
            "Expected an AArch64 ET_DYN ELF")
    return actual


def canonical_info(name):
    info = zipfile.ZipInfo(name, DATE)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = ((stat.S_IFDIR | 0o755) << 16 | 0x10) if name.endswith("/") else (
        (stat.S_IFREG | 0o644) << 16)
    return info


def archive_index(archive, *, canonical=False, apk=False):
    entries = archive.infolist()
    require(len(entries) <= (50000 if apk else 4096), "Too many ZIP members")
    require(sum(info.file_size for info in entries) <= (2 * GIB if apk else 512 * CHUNK),
            "ZIP uncompressed content exceeds the supported size limit")
    names = [info.filename for info in entries]
    require(len(names) == len(set(names)), "Duplicate ZIP member")
    if canonical:
        require(names == sorted(names) and not archive.comment, "Noncanonical ZIP order or comment")
    for info in entries:
        name = info.filename
        parts = name.rstrip("/").split("/")
        require(info.orig_filename == name and name and not name.startswith("/")
                and "\\" not in name and ":" not in name
                and all(part not in ("", ".", "..") for part in parts)
                and not any(ord(char) < 32 or ord(char) == 127 for char in name),
                f"Unsafe ZIP member name: {name!r}")
        mode = info.external_attr >> 16
        kind = stat.S_IFMT(mode)
        require(kind in (0, stat.S_IFDIR if info.is_dir() else stat.S_IFREG),
                f"Nonregular ZIP member: {name}")
        require(not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                f"Encrypted or unsupported ZIP member: {name}")
        require(not info.is_dir() or info.file_size == 0, f"Nonempty ZIP directory: {name}")
        if canonical:
            expected = canonical_info(name)
            require(info.date_time == DATE and info.create_system == 3
                    and info.compress_type == zipfile.ZIP_STORED
                    and info.external_attr == expected.external_attr
                    and not info.extra and not info.comment and not info.internal_attr,
                    f"Noncanonical ZIP metadata: {name}")
    return {info.filename: info for info in entries}


def member_identity(archive, info):
    with archive.open(info) as stream:
        actual = stream_identity(stream)
    require(actual["bytes"] == info.file_size, f"Incorrect ZIP member length: {info.filename}")
    return actual


def archive_inventory(path, *, canonical=False):
    with zipfile.ZipFile(path) as archive:
        return {name: member_identity(archive, info)
                for name, info in archive_index(archive, canonical=canonical).items()}


def convert_aars(aar, library, full_path, companion_path):
    """Deterministically transform ZIP members; production pins are checked by prepare()."""
    with zipfile.ZipFile(aar) as source, zipfile.ZipFile(full_path, "x", allowZip64=False) as full, \
            zipfile.ZipFile(companion_path, "x", allowZip64=False) as companion:
        index = archive_index(source)
        require(REQUIRED_MEMBERS <= set(index), "Original AAR is missing required Java/JNI/manifest members")
        for name in sorted(index):
            with ExitStack() as stack:
                if name == MEMBER:
                    incoming = stack.enter_context(Path(library).open("rb"))
                    destinations = [stack.enter_context(full.open(canonical_info(name), "w"))]
                else:
                    incoming = stack.enter_context(source.open(index[name]))
                    destinations = [stack.enter_context(output.open(canonical_info(name), "w"))
                                    for output in (full, companion)]
                stream_identity(incoming, destinations)


def compare_members(actual, expected, label):
    missing, extra = sorted(set(expected) - set(actual)), sorted(set(actual) - set(expected))
    changed = sorted(name for name in set(expected) & set(actual) if actual[name] != expected[name])
    require(not (missing or extra or changed),
            f"{label} members differ: missing={missing}, extra={extra}, changed={changed}")


def verify_aars(full_path, companion_path, library, aar=None):
    full = archive_inventory(full_path, canonical=True)
    companion = archive_inventory(companion_path, canonical=True)
    require(REQUIRED_MEMBERS <= set(full), "Full AAR is missing required Java/JNI/manifest members")
    match(full[MEMBER], library, "full AAR replacement member")
    compare_members(companion, {name: value for name, value in full.items() if name != MEMBER},
                    "Companion AAR")
    comparison = {"originalCompared": False, "fullMemberCount": len(full),
                  "companionMemberCount": len(companion)}
    if aar is not None:
        match(file_identity(aar), ORIGINAL_AAR, "official AAR")
        original = archive_inventory(aar)
        require(REQUIRED_MEMBERS <= set(original), "Original AAR is missing required members")
        compare_members(full, {**original, MEMBER: identity(library, "library")}, "Full AAR")
        comparison.update({"originalCompared": True, "originalAar": ORIGINAL_AAR,
                           "replacement": {"path": MEMBER, "before": original[MEMBER], "after": full[MEMBER]},
                           "unchangedMembers": [{"path": name, **original[name]} for name in sorted(original)
                                                if name != MEMBER]})
        match(file_identity(aar), ORIGINAL_AAR, "official AAR after comparison")
    return comparison


def verify_bundle(directory, lock, aar=None):
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), f"Not a regular output directory: {directory}")
    outputs = {name: file_identity(directory / filename) for name, filename in OUTPUTS.items()}
    check_library(directory / OUTPUTS["library"], lock["library"])
    if "outputs" in lock:
        for name, value in outputs.items():
            match(value, lock["outputs"][name], name)
    comparison = verify_aars(directory / OUTPUTS["fullAar"], directory / OUTPUTS["companionAar"],
                             lock["library"], aar)
    return {"outputs": outputs, "memberComparison": comparison}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def prepare(aar, library, directory, lock, report):
    match(file_identity(aar), ORIGINAL_AAR, "official AAR")
    check_library(library, lock["library"])
    directory = Path(directory)
    require(not directory.exists() and not directory.is_symlink(),
            f"Output already exists; verify it or choose a new directory: {directory}")
    with zipfile.ZipFile(aar) as archive:
        index = archive_index(archive)
        require(REQUIRED_MEMBERS <= set(index), "Original AAR is missing required members")
        estimate = 2 * sum(info.file_size for info in index.values()) + 3 * lock["library"]["bytes"] + CHUNK
    require(estimate < 5 * GIB, "Preparation exceeds the 5 GiB temporary-data budget")
    directory.parent.mkdir(parents=True, exist_ok=True)
    require(shutil.disk_usage(directory.parent).free >= estimate + 5 * GIB,
            "Insufficient free space for outputs and a 5 GiB reserve")
    staging = Path(tempfile.mkdtemp(prefix=".ort-runtime-", dir=directory.parent))
    try:
        copied = staging / OUTPUTS["library"]
        copied.parent.mkdir()
        with Path(library).open("rb") as incoming, copied.open("xb") as outgoing:
            stream_identity(incoming, [outgoing])
        check_library(copied, lock["library"])
        convert_aars(aar, copied, staging / OUTPUTS["fullAar"], staging / OUTPUTS["companionAar"])
        report.update(verify_bundle(staging, lock, aar))
        report["outputDirectory"] = str(directory.resolve())
        write_json(staging / "preparation-receipt.json", report)
        require(not directory.exists() and not directory.is_symlink(), "Output directory appeared during preparation")
        staging.rename(directory)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return report


def verify_apk(apk, lock):
    contract, digest = read_json(BASELINE)
    require(digest == BASELINE_SHA256, "Shipped ABI inventory changed; review the baseline explicitly")
    require(contract["baseline"]["apk"]["sha256"] == OLD_APK_SHA256,
            "Unexpected shipped APK baseline")
    libraries = contract["baseline"]["libraries"]
    expected = {entry["apkMember"]: identity(entry, entry["apkMember"]) for entry in libraries}
    require(len(libraries) == len(expected) == 12, "Expected the 12 shipped native libraries")
    expected["lib/arm64-v8a/libonnxruntime.so"] = identity(lock["library"], "library")
    apk_identity = file_identity(apk)
    with zipfile.ZipFile(apk) as archive:
        index = archive_index(archive, apk=True)
        native_names = {name for name, info in index.items() if name.startswith("lib/") and not info.is_dir()}
        require(native_names == set(expected),
                f"APK native inventory differs: missing={sorted(set(expected) - native_names)}, "
                f"extra={sorted(native_names - set(expected))}")
        checked = []
        for name in sorted(expected):
            actual = member_identity(archive, index[name])
            match(actual, expected[name], name)
            checked.append({"path": name, **actual})
    match(file_identity(apk), apk_identity, "APK after comparison")
    return {"apk": apk_identity, "baselineContractSha256": digest, "libraries": checked,
            "unchangedOtherLibraryCount": 11,
            "scope": "Default prebuilt APK native bytes only; resources, signature, ZIP alignment and runtime behavior are separate gates."}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="Default output: vendor/ort-runtime. Full/companion AAR names and the ELF path are fixed by OUTPUTS in this script.")
    locks = parser.add_mutually_exclusive_group(required=True)
    locks.add_argument("--candidate-lock", type=Path, help="Explicit candidate JSON lock; never modified")
    locks.add_argument("--accepted-lock", type=Path, help="Explicit accepted JSON lock; never modified")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--verify-only", action="store_true", help="Verify an existing runtime output directory")
    modes.add_argument("--verify-native-input", type=Path, metavar="ELF", help="Verify a source-build linker input against an accepted lock")
    modes.add_argument("--verify-apk", type=Path, metavar="APK", help="Verify exactly 12 native libraries in a default prebuilt APK")
    parser.add_argument("--aar", type=Path, help="Pinned official AAR; required for preparation and candidate verification")
    parser.add_argument("--library", type=Path, help="Replacement ELF; required for preparation")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="Runtime directory (default: vendor/ort-runtime)")
    parser.add_argument("--receipt", type=Path, help="New JSON receipt file for verification; existing files are never overwritten")
    args = parser.parse_args()
    accepted = args.accepted_lock is not None
    lock_path = args.accepted_lock if accepted else args.candidate_lock
    mode = ("verify-only" if args.verify_only else "verify-native-input" if args.verify_native_input else
            "verify-apk" if args.verify_apk else "prepare")
    if mode in ("verify-native-input", "verify-apk") and not accepted:
        parser.error(f"{mode} requires --accepted-lock")
    if (mode == "prepare" or mode == "verify-only" and not accepted) and args.aar is None:
        parser.error("This operation requires --aar")
    if mode == "prepare" and args.library is None:
        parser.error("Preparation requires --library")
    if mode == "prepare" and args.receipt:
        parser.error("Preparation writes output-dir/preparation-receipt.json; --receipt is for verification")
    if mode != "prepare" and args.library:
        parser.error("--library is only used for preparation")
    if mode in ("verify-native-input", "verify-apk") and args.aar:
        parser.error("--aar is only used for preparation or --verify-only")
    lock, lock_hash = load_lock(lock_path, accepted)
    report = {"schemaVersion": 1, "kind": "lantype-ort-runtime-receipt", "ok": True, "mode": mode,
              "acceptedLock": accepted, "lockSha256": lock_hash, "nativeCodeExecuted": False,
              "runtimeAcceptancePerformed": False}
    if mode == "prepare":
        prepare(args.aar, args.library, args.output_dir, lock, report)
        print(json.dumps({key: report[key] for key in ("ok", "mode", "acceptedLock", "outputs", "outputDirectory")}, indent=2))
        return
    if mode == "verify-only":
        report.update(verify_bundle(args.output_dir, lock, args.aar))
    elif mode == "verify-native-input":
        report["library"] = check_library(args.verify_native_input, lock["library"])
        report["scope"] = "Linker-input bytes only; no linking or native execution performed."
    else:
        report.update(verify_apk(args.verify_apk, lock))
    if args.receipt:
        write_json(args.receipt, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, zipfile.BadZipFile, EOFError, KeyError, TypeError) as error:
        print(json.dumps({"ok": False, "error": str(error), "nativeCodeExecuted": False}), file=sys.stderr)
        sys.exit(1)
