#!/usr/bin/env python3
"""Prepare one locked official Android image without a temporary archive on disk.

The first download verifies Google's archive size/SHA-1 and records SHA-256 for
each 8 MiB block. ZipFile then reads HTTP ranges, accepting only those same
verified blocks. Zero blocks become sparse extents without changing file bytes.
No license is accepted, no emulator starts, and no Android test runs here.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from urllib.request import Request, urlopen
import zipfile

MIB = 1024 ** 2
BLOCK = 8 * MIB
SPARSE_BLOCK = 64 * 1024
RESERVE = 256 * MIB
PACKAGE = "system-images;android-35;google_apis;x86_64"
ARCHIVE_URL = "https://dl.google.com/android/repository/sys-img/google_apis/x86_64-35_r09.zip"
ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def reserve(root, additional=0):
    require(shutil.disk_usage(root).free > RESERVE + additional,
            "System-image preparation reached the 256 MiB work-volume reserve")


def open_archive(url, *, start=None, end=None):
    headers = {"User-Agent": "LanType-locked-Android-image", "Accept-Encoding": "identity"}
    if start is not None:
        headers["Range"] = f"bytes={start}-{end}"
    response = urlopen(Request(url, headers=headers), timeout=60)
    try:
        require(response.geturl() == ARCHIVE_URL, "System-image download left the fixed official URL")
        require(response.headers.get("Content-Encoding", "identity") == "identity", "Unexpected HTTP content encoding")
        require(response.status == (200 if start is None else 206),
                "The official image server did not honor the requested download/range")
        return response
    except BaseException:
        response.close()
        raise


def read_exact(stream, count):
    parts, remaining = [], count
    while remaining:
        part = stream.read(remaining)
        require(part, "Official archive ended before its locked byte count")
        parts.append(part)
        remaining -= len(part)
    return b"".join(parts)


def fingerprint_archive(lock, root):
    archive = lock["archive"]
    # Refuse an unsupported range server before spending a complete first pass.
    with open_archive(archive["url"], start=0, end=0) as response:
        require(response.headers.get("Content-Range") == f"bytes 0-0/{archive['bytes']}" and
                response.read(2) == b"P", "Official image range preflight failed")
    sha1, sha256, chunks, count = hashlib.sha1(), hashlib.sha256(), [], 0
    with open_archive(archive["url"]) as response:
        declared = response.headers.get("Content-Length")
        require(declared is None or int(declared) == archive["bytes"], "Official archive Content-Length changed")
        while count < archive["bytes"]:
            reserve(root)
            block = read_exact(response, min(BLOCK, archive["bytes"] - count))
            sha1.update(block)
            sha256.update(block)
            chunks.append(hashlib.sha256(block).hexdigest())
            count += len(block)
            if len(chunks) % 32 == 0:
                print(json.dumps({"phase": "verify-official-archive", "bytesRead": count,
                                  "archiveBytes": archive["bytes"]}), flush=True)
        require(not response.read(1), "Official archive exceeds its locked byte count")
    require(sha1.hexdigest() == archive["sha1"], "Official archive SHA-1 differs from the fixed Google metadata")
    return {"bytes": count, "sha1": sha1.hexdigest(), "sha256": sha256.hexdigest(),
            "blockBytes": BLOCK, "blockSha256": chunks, "archiveStoredOnDisk": False}


class VerifiedRangeReader(io.RawIOBase):
    """Seekable view that only returns bytes bound to the verified first pass."""
    def __init__(self, url, fingerprint, root):
        super().__init__()
        self.url, self.fingerprint, self.root = url, fingerprint, root
        self.position, self.requests, self.received = 0, 0, 0
        self.cache = OrderedDict()

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=os.SEEK_SET):
        require(whence in (os.SEEK_SET, os.SEEK_CUR, os.SEEK_END), "Invalid ZIP seek mode")
        origin = (0 if whence == os.SEEK_SET else self.position if whence == os.SEEK_CUR
                  else self.fingerprint["bytes"])
        require(origin + offset >= 0, "ZIP seek before the archive")
        self.position = origin + offset
        return self.position

    def block(self, number):
        reserve(self.root)
        if number in self.cache:
            self.cache.move_to_end(number)
            return self.cache[number]
        start = number * BLOCK
        end = min(start + BLOCK, self.fingerprint["bytes"]) - 1
        with open_archive(self.url, start=start, end=end) as response:
            require(response.headers.get("Content-Range") == f"bytes {start}-{end}/{self.fingerprint['bytes']}",
                    "Official server returned a different range or archive size")
            block = response.read(end - start + 2)
        require(len(block) == end - start + 1 and
                hashlib.sha256(block).hexdigest() == self.fingerprint["blockSha256"][number],
                "An HTTP range differs from the already verified official archive")
        self.requests += 1
        self.received += len(block)
        self.cache[number] = block
        self.cache.move_to_end(number)
        while len(self.cache) > 2:
            self.cache.popitem(last=False)
        return block

    def read(self, count=-1):
        remaining = max(0, self.fingerprint["bytes"] - self.position)
        count = remaining if count is None or count < 0 else min(count, remaining)
        require(count <= 32 * MIB, "ZIP requested an unexpectedly large read")
        parts = []
        while count:
            number, offset = divmod(self.position, BLOCK)
            part = self.block(number)[offset:offset + count]
            require(part, "Empty verified archive block")
            parts.append(part)
            self.position += len(part)
            count -= len(part)
        return b"".join(parts)


def member_index(source):
    entries = source.infolist()
    require(1 <= len(entries) <= 4096, "Unexpected system-image ZIP member count")
    require(sum(item.file_size for item in entries) <= 12 * 1024 ** 3, "System-image logical contents exceed 12 GiB")
    names = [item.filename for item in entries]
    require(len(names) == len(set(names)), "Duplicate system-image ZIP member")
    for item in entries:
        name = item.filename
        parts = name.rstrip("/").split("/")
        require(item.orig_filename == name and parts[0] == "x86_64" and
                all(part not in ("", ".", "..") for part in parts) and
                "\\" not in name and ":" not in name and
                not any(ord(char) < 32 or ord(char) == 127 for char in name), "Unsafe system-image member path")
        kind = stat.S_IFMT(item.external_attr >> 16)
        require(kind in (0, stat.S_IFDIR if item.is_dir() else stat.S_IFREG), "Nonregular system-image member")
        require(not item.flag_bits & 1 and item.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                "Unsupported or encrypted system-image member")
        require(item.file_size <= 8 * 1024 ** 3 and (not item.is_dir() or item.file_size == 0),
                "Unexpected system-image member size")
    require({"x86_64/source.properties", "x86_64/system.img", "x86_64/vendor.img", "x86_64/kernel-ranchu",
             "x86_64/ramdisk.img", "x86_64/build.prop"} <= set(names), "Incomplete official system image")
    return entries


def write_sparse(incoming, target, expected_bytes, root):
    digest, count, zero_bytes = hashlib.sha256(), 0, 0
    with target.open("xb") as outgoing:
        while block := incoming.read(MIB):
            require(count + len(block) <= expected_bytes, "Inflated system-image member exceeds its size")
            digest.update(block)
            count += len(block)
            reserve(root, MIB)
            for offset in range(0, len(block), SPARSE_BLOCK):
                part = block[offset:offset + SPARSE_BLOCK]
                if not part.strip(b"\0"):
                    outgoing.seek(len(part), os.SEEK_CUR)
                    zero_bytes += len(part)
                else:
                    outgoing.write(part)
        require(count == expected_bytes, "Inflated system-image member has the wrong size")
        outgoing.truncate(count)
        outgoing.flush()
        allocated = os.fstat(outgoing.fileno()).st_blocks * 512
    return {"bytes": count, "sha256": digest.hexdigest(), "allocatedBytes": allocated,
            "zeroBytesStoredAsHoles": zero_bytes, "sparseBlockBytes": SPARSE_BLOCK}


def prepare(lock_path, work_root, sdk, evidence):
    lock_bytes = lock_path.read_bytes()
    lock = json.loads(lock_bytes)
    require(lock.get("schemaVersion") == 1 and lock.get("packageId") == PACKAGE and lock.get("revision") == 9,
            "Expected the fixed official API 35 Google APIs x86_64 revision 9 lock")
    archive = lock["archive"]
    require(archive.get("url") == ARCHIVE_URL and archive.get("bytes") == 1738815903 and
            archive.get("sha1") == "0103e6dab21290c4b9d16550a3ce99476f884eef", "Official image archive identity changed")
    work_root = work_root.absolute()
    require(work_root.resolve() == work_root and os.path.ismount(work_root) and
            work_root.stat().st_dev != work_root.parent.stat().st_dev and
            0 < shutil.disk_usage(work_root).total <= 4608 * MIB, "Expected an independent work mount of at most 4.5 GiB")
    require(sdk.absolute() == work_root / "sdk" and sdk.resolve() == sdk.absolute() and sdk.is_dir(), "Unexpected SDK overlay")
    require(evidence.absolute().resolve() == evidence.absolute() and evidence.is_dir() and
            evidence.absolute().is_relative_to(work_root / "evidence"), "Evidence must stay in the work volume")
    license_hash = lock["license"]["acceptedSha1"]
    require(license_hash == "24333f8a63b6825ea9c5514f83c2829b004d1fee" and
            lock["license"]["id"] == "android-sdk-license", "Invalid license identity")
    license_file = sdk / "licenses/android-sdk-license"
    require(license_file.is_file() and not license_file.is_symlink() and license_file.stat().st_size <= MIB and
            license_file.resolve().is_relative_to(sdk) and
            license_hash in license_file.read_text().splitlines(),
            "This SDK license has not already been accepted; no acceptance is performed")
    license_file_sha256 = hashlib.sha256(license_file.read_bytes()).hexdigest()
    destination = sdk / "system-images/android-35/google_apis/x86_64"
    require(not destination.exists() and not destination.is_symlink(), "System-image destination already exists; preserved")
    reserve(work_root)
    fingerprint = fingerprint_archive(lock, work_root)
    save(evidence / "image-archive-identity.json", {"lockSha256": hashlib.sha256(lock_bytes).hexdigest(),
         "url": ARCHIVE_URL, "licenseAlreadyAccepted": True, "acceptedLicenseSha1": license_hash,
         "licenseFileSha256": license_file_sha256, "licenseAcceptedByThisTool": False, **fingerprint})
    staging = Path(tempfile.mkdtemp(prefix="image-unpack-", dir=work_root))
    members = []
    try:
        with VerifiedRangeReader(ARCHIVE_URL, fingerprint, work_root) as reader, zipfile.ZipFile(reader) as source:
            entries = member_index(source)
            for item in entries:
                target = staging / item.filename
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as incoming:
                    identity = write_sparse(incoming, target, item.file_size, work_root)
                target.chmod(0o755 if item.external_attr >> 16 & 0o111 else 0o644)
                members.append({"path": item.filename, "zipCrc32": f"{item.CRC:08x}", **identity})
                print(json.dumps({"phase": "extract-verified-image", **members[-1]}), flush=True)
            transfer = {"rangeRequests": reader.requests, "rangeBytesReceived": reader.received,
                        "rangeCacheBlockLimit": 2, "rangeBytesBoundToVerifiedFirstPass": True}
        properties = staging / "x86_64/source.properties"
        require(hashlib.sha256(properties.read_bytes()).hexdigest() == lock["sourceProperties"]["sha256"],
                "Extracted source.properties bytes differ from the independently read official member")
        props = dict(line.split("=", 1) for line in properties.read_text().splitlines()
                     if "=" in line and not line.lstrip().startswith("#"))
        props = {key.strip(): value.strip() for key, value in props.items()}
        require(props.get("AndroidVersion.ApiLevel") == "35" and props.get("SystemImage.Abi") == "x86_64" and
                props.get("SystemImage.TagId") == "google_apis" and props.get("Pkg.Revision") in ("9", "9.0.0"),
                "Extracted source.properties does not match the locked image")
        destination.parent.mkdir(parents=True, exist_ok=True)
        require(destination.parent.resolve() == destination.parent and
                destination.parent.stat().st_dev == work_root.stat().st_dev and
                not destination.exists() and not destination.is_symlink(), "Image destination changed during preparation")
        (staging / "x86_64").rename(destination)
        save(evidence / "image-files.json", {"schemaVersion": 1, "packageId": PACKAGE, "revision": 9,
             "archiveSha256": fingerprint["sha256"], "files": members, "transfer": transfer,
             "logicalBytes": sum(item["bytes"] for item in members),
             "allocatedBytes": sum(item["allocatedBytes"] for item in members),
             "zeroBytesStoredAsHoles": sum(item["zeroBytesStoredAsHoles"] for item in members),
             "sdkRegistrationPending": True, "androidTestExecuted": False, "licenseAcceptedByThisTool": False})
    finally:
        shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=ROOT / "docs/qa/android-api35-image.lock.json")
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--sdk-root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(args.lock, args.work_root, args.sdk_root, args.evidence)
        return 0
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile, EOFError) as error:
        print(json.dumps({"stage": "prepare-system-image", "error": str(error), "androidTestExecuted": False}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
