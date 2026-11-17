#!/usr/bin/env python3
"""Collect fixed public source archives only; never execute upstream code.

Initial computed archive hashes are collection results awaiting review, not
previously trusted pins. --verify checks the independent supplement, not the
old 70-source lock. An independently reviewed ZIP hash establishes its identity.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
NAME = "LanType-native-source-webgpu-supplement-v1"
ZIP_NAME = NAME + ".zip"
BASE_LOCK = "docs/licensing/native-sources.lock.json"
ORT_COMMIT = "da9b5e364c465de65c49d91e696cd6485270757f"
DAWN_COMMIT = "ec7b457e5bb1fcec6f59733c4f3dd84d2f885a38"
DAWN_SHA1 = "d4d64d1729104b61e654073566f1a376e16cad92"
ELF_SHA256 = "f826d8efb03adf0a84f10e7ba408f9d4cd11b0a2ccd8d08aeb0f7451fb50cacc"
ELF_BYTES = 28637280
APPROVED_REPOSITORIES = {
    "ort-dawn": "https://github.com/google/dawn",
    "dawn-spirv-headers": "https://github.com/KhronosGroup/SPIRV-Headers",
    "dawn-spirv-tools": "https://github.com/KhronosGroup/SPIRV-Tools",
    "dawn-vulkan-headers": "https://github.com/KhronosGroup/Vulkan-Headers",
    "dawn-vulkan-utility-libraries": "https://github.com/KhronosGroup/Vulkan-Utility-Libraries",
    "dawn-jinja2": "https://chromium.googlesource.com/chromium/src/third_party/jinja2",
    "dawn-markupsafe": "https://chromium.googlesource.com/chromium/src/third_party/markupsafe",
}
MIB = 1024 * 1024
MAX_ARCHIVE_BYTES = 384 * MIB
MAX_TOTAL_ARCHIVE_BYTES = 1024 * MIB
MAX_UNPACKED_BYTES = 2048 * MIB
MAX_MEMBERS = 200000
MAX_LICENSE_BYTES = 2 * MIB
MAX_SMALL_BYTES = 8 * MIB
MAX_PLAN_BYTES = MIB
MIN_FREE_BYTES = 5 * 1024**3
TOTAL_SECONDS = 1500
DOWNLOAD_SECONDS = 360
CHUNK = MIB


class CollectionError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CollectionError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path, maximum=MAX_PLAN_BYTES):
    require(path.is_file() and not path.is_symlink(), "Expected regular JSON file: " + str(path))
    require(path.stat().st_size <= maximum, "JSON input exceeds size limit")
    data = path.read_bytes()
    return json.loads(data, object_pairs_hook=unique_object), data


def safe_path(name, *, directory=False):
    require(isinstance(name, str) and 0 < len(name) <= 2048, "Invalid archive/member path")
    require(not any(ord(char) < 32 or ord(char) == 127 for char in name), "Control character in path")
    require("\\" not in name and ":" not in name and not name.startswith("/"), "Absolute/Windows path rejected: " + name)
    value = name[:-1] if directory and name.endswith("/") else name
    parts = value.split("/")
    require(all(part not in ("", ".", "..") for part in parts), "Empty/dot/traversal path rejected: " + name)
    return "/".join(parts)


def hex_digest(value, length):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value) is not None


def check_url(entry, url, *, redirect=False):
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.port in (None, 443) and not parsed.query and not parsed.fragment,
            "Only credential-free fixed HTTPS archive URLs are allowed")
    require("%" not in parsed.path, "Encoded archive URL path rejected")
    repository, commit = entry["repository"], entry["commit"]
    if repository.startswith("https://github.com/"):
        project = repository.removeprefix("https://github.com/")
        allowed = {
            "https://github.com/" + project + "/archive/" + commit + ".zip",
            "https://codeload.github.com/" + project + "/zip/" + commit,
        }
    else:
        allowed = {repository + "/+archive/" + commit + ".tar.gz"}
    require(url in allowed, "Archive URL/redirect differs from the approved repository and commit: " + url)


def validate_plan(plan, base):
    require(plan.get("schemaVersion") == 1, "Unsupported source plan schema")
    sources = plan.get("sources")
    require(isinstance(sources, list) and len(sources) == len(APPROVED_REPOSITORIES), "Expected exactly seven approved new sources")
    ids, filenames, installs = set(), set(), set()
    for entry in sources:
        identity = entry.get("id")
        require(identity in APPROVED_REPOSITORIES and identity not in ids, "Unknown or duplicate source id")
        ids.add(identity)
        require(entry.get("repository") == APPROVED_REPOSITORIES[identity], "Repository is not the reviewed official source")
        require(hex_digest(entry.get("commit"), 40), "Source needs an exact lowercase 40-hex commit")
        check_url(entry, entry.get("archiveUrl", ""))
        filename = safe_path(entry.get("archiveFilename"))
        require("/" not in filename and filename not in filenames, "Duplicate or non-basename archive filename")
        filenames.add(filename)
        github = entry["repository"].startswith("https://github.com/")
        require(entry.get("archiveLayout") == ("single-root-directory" if github else "flat"), "Archive layout does not match this approved source")
        require(filename.endswith(".zip" if github else ".tar.gz"), "Unexpected archive type")
        install = safe_path(entry.get("installPath"))
        require((install == "vendor/native-sources/runtime-onnxruntime-dawn"
                 or install.startswith("vendor/native-sources/runtime-onnxruntime-dawn/"))
                and install not in installs and "assets" not in PurePosixPath(install).parts,
                "Unexpected or duplicate installation destination")
        installs.add(install)
        require(isinstance(entry.get("reason"), str) and entry["reason"].strip()
                and isinstance(entry.get("license"), str) and entry["license"].strip(), "Missing license/reason declaration")
        licenses = entry.get("licenseFiles")
        require(isinstance(licenses, list) and 0 < len(licenses) <= 32, "Missing/bounded licenseFiles list required")
        require(len(set(licenses)) == len(licenses), "Duplicate expected license path")
        for name in licenses:
            safe_path(name)
        metadata = entry.get("licenseMetadata", [])
        require(isinstance(metadata, list) and len(metadata) == len(licenses), "Every license needs reviewed byte/hash metadata")
        require({item.get("path") for item in metadata} == set(licenses), "License metadata paths differ from licenseFiles")
        for item in metadata:
            require(hex_digest(item.get("sha256"), 64) and type(item.get("bytes")) is int
                    and 0 < item["bytes"] <= MAX_LICENSE_BYTES, "Invalid expected license identity")
        if entry.get("archiveSha256") is not None:
            require(hex_digest(entry["archiveSha256"], 64), "Invalid pre-existing archive SHA-256")
        if entry.get("archiveBytes") is not None:
            require(type(entry["archiveBytes"]) is int and 0 < entry["archiveBytes"] <= MAX_ARCHIVE_BYTES, "Invalid pre-existing archive size")
        if entry.get("expectedArchiveSha1") is not None:
            require(hex_digest(entry["expectedArchiveSha1"], 40), "Invalid upstream SHA-1 pin")
    dawn = next(item for item in sources if item["id"] == "ort-dawn")
    require(dawn["commit"] == DAWN_COMMIT and dawn.get("expectedArchiveSha1") == DAWN_SHA1, "Dawn must match the fixed ORT deps.txt pin")
    binary = plan.get("binaryEvidence", {})
    require(binary.get("sha256") == ELF_SHA256 and binary.get("bytes") == ELF_BYTES
            and binary.get("apkMember") == "lib/arm64-v8a/libonnxruntime.so"
            and binary.get("appliesToVersions") == ["1.1.0", "1.1.1"], "Plan does not identify the unchanged shipped ORT ELF")
    reused = plan.get("reusedSources")
    require(isinstance(reused, list) and {item.get("id") for item in reused}
            == {"runtime-onnxruntime", "onnx-dependency-abseil_cpp"} and len(reused) == 2, "Unexpected reused-source inventory")
    base_entries = {item["id"]: item for item in base["sources"]}
    for item in reused:
        original = base_entries.get(item["id"], {})
        require(item.get("sourceLock") == BASE_LOCK and all(item.get(key) == original.get(old)
                for key, old in (("archiveFilename", "archive_file"), ("archiveBytes", "archive_bytes"),
                                 ("archiveSha256", "archive_sha256"), ("installPath", "installPath"))),
                "Reused source differs from the existing base lock: " + item["id"])
    require(isinstance(plan.get("omittedOptional"), list) and len(plan["omittedOptional"]) <= 64, "Missing bounded omitted dependency explanation")
    patches = plan.get("ortPatches")
    require(isinstance(patches, list) and len(patches) == 7
            and sorted(item.get("applyOrder", 0) for item in patches) == list(range(1, 8)), "Expected seven ordered ORT patch references")
    patch_paths = set()
    for item in patches:
        path = safe_path(item.get("path"))
        require(path.startswith("cmake/patches/dawn/") and path.endswith(".patch") and path not in patch_paths,
                "Unexpected or duplicate ORT patch path")
        patch_paths.add(path)
        require(item.get("commit") == ORT_COMMIT and item.get("repository") == "https://github.com/microsoft/onnxruntime"
                and item.get("sourceArchiveId") == "runtime-onnxruntime" and hex_digest(item.get("sha256"), 64)
                and type(item.get("bytes")) is int and 0 < item["bytes"] < MAX_LICENSE_BYTES,
                "Invalid fixed ORT patch identity")
    for entry in sources:
        require(set(entry.get("dependsOn", [])) <= ids | set(base_entries), "Unresolved source dependency id")


class Deadline:
    def __init__(self, seconds=TOTAL_SECONDS):
        self.end = time.monotonic() + seconds

    def remaining(self):
        result = self.end - time.monotonic()
        require(result > 0, "Collection time budget exhausted")
        return result


class FixedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, entry):
        self.entry = entry

    def redirect_request(self, request, response, code, message, headers, newurl):
        check_url(self.entry, newurl, redirect=True)
        return super().redirect_request(request, response, code, message, headers, newurl)


def download(entry, destination, deadline, already_downloaded):
    limit = min(MAX_ARCHIVE_BYTES, MAX_TOTAL_ARCHIVE_BYTES - already_downloaded)
    require(limit > 0, "Total source download limit reached")
    end = min(deadline.end, time.monotonic() + DOWNLOAD_SECONDS)
    partial = destination.with_name(destination.name + ".partial")
    require(not destination.exists() and not partial.exists(), "Refusing to overwrite source archive")
    opener = urllib.request.build_opener(FixedRedirect(entry))
    request = urllib.request.Request(entry["archiveUrl"], headers={"User-Agent": "LanType-source-supplement/1", "Accept-Encoding": "identity"})
    count, digest, legacy = 0, hashlib.sha256(), hashlib.sha1()
    with opener.open(request, timeout=min(20, deadline.remaining())) as response, partial.open("xb") as target:
        check_url(entry, response.geturl(), redirect=True)
        require(response.status == 200, "Archive server did not return HTTP 200")
        declared = response.headers.get("Content-Length")
        if declared is not None:
            require(declared.isdigit() and int(declared) <= limit, "Archive Content-Length exceeds limit or is invalid")
        while True:
            deadline.remaining()
            require(time.monotonic() < end, "Per-source download deadline reached")
            # read1 performs at most one buffered/socket read. A server sending
            # a slow trickle cannot keep a full-CHUNK read alive indefinitely
            # and bypass the monotonic deadline checks between reads.
            block = response.read1(CHUNK)
            if not block:
                break
            count += len(block)
            require(count <= limit, "Downloaded archive exceeds byte budget")
            target.write(block)
            digest.update(block)
            legacy.update(block)
    require(count > 0 and (declared is None or count == int(declared)), "Empty or truncated source download")
    require(entry.get("archiveBytes") in (None, count), "Archive bytes differ from reviewed plan pin")
    require(entry.get("archiveSha256") in (None, digest.hexdigest()), "Archive SHA-256 differs from reviewed plan pin")
    require(entry.get("expectedArchiveSha1") in (None, legacy.hexdigest()), "Archive differs from fixed upstream SHA-1 pin")
    partial.rename(destination)
    return {"archiveBytes": count, "archiveSha256": digest.hexdigest(), "archiveSha1": legacy.hexdigest(),
            "archiveIdentityStatus": "matched-existing-plan-pin" if entry.get("archiveSha256") else "first-collection-awaiting-review"}


class BoundedReader:
    def __init__(self, stream, deadline):
        self.stream, self.deadline, self.count = stream, deadline, 0

    def read(self, size=-1):
        self.deadline.remaining()
        require(size >= 0, "Unbounded decompression read rejected")
        data = self.stream.read(min(size, MAX_UNPACKED_BYTES - self.count + 1))
        self.count += len(data)
        require(self.count <= MAX_UNPACKED_BYTES, "Tar decompressed-byte limit exceeded")
        return data


class MemberAudit:
    def __init__(self, entry, deadline):
        self.entry, self.deadline = entry, deadline
        self.prefix = (entry["repository"].rsplit("/", 1)[1] + "-" + entry["commit"]
                       if entry["archiveLayout"] == "single-root-directory" else "")
        self.members, self.links, self.licenses = {}, {}, {}
        self.expected = {item["path"]: item for item in entry["licenseMetadata"]}
        self.total = 0

    def add(self, name, kind, size, read, target=None):
        self.deadline.remaining()
        full = safe_path(name, directory=kind == "directory")
        require(full not in self.members, "Duplicate archive member: " + full)
        require(len(self.members) < MAX_MEMBERS, "Archive member-count limit exceeded")
        require(type(size) is int and 0 <= size <= MAX_UNPACKED_BYTES, "Invalid member size")
        self.total += size
        require(self.total <= MAX_UNPACKED_BYTES, "Archive unpacked-size limit exceeded")
        self.members[full] = kind
        if self.prefix:
            require(full == self.prefix or full.startswith(self.prefix + "/"), "Archive member is outside the exact commit root")
            relative = full[len(self.prefix):].lstrip("/")
            require(relative or kind == "directory", "Archive root must be a directory")
        else:
            relative = full
        if kind in ("symlink", "hardlink"):
            if target is None:
                require(size <= 4096, "Oversized symlink payload")
                target = read().decode("utf-8", "strict")
            require(target and not target.startswith("/") and "\\" not in target and ":" not in target
                    and not any(ord(char) < 32 or ord(char) == 127 for char in target), "Unsafe link target")
            parts = full.split("/")[:-1] if kind == "symlink" else []
            for part in target.split("/"):
                if part in ("", "."):
                    continue
                if part == "..":
                    require(len(parts) > (1 if self.prefix else 0), "Link escapes archive root")
                    parts.pop()
                else:
                    parts.append(part)
            resolved = "/".join(parts)
            require(resolved and (not self.prefix or resolved == self.prefix or resolved.startswith(self.prefix + "/")), "Link leaves the source root")
            self.links[full] = resolved
        if relative in self.expected:
            require(kind == "file", "Expected license is not a regular file: " + relative)
            expected = self.expected[relative]
            require(size == expected["bytes"] and size <= MAX_LICENSE_BYTES, "License size differs from reviewed metadata: " + relative)
            data = read()
            require(len(data) == size and data.strip() and b"\0" not in data
                    and sha256(data) == expected["sha256"], "License content differs from reviewed metadata: " + relative)
            self.licenses[relative] = data

    def finish(self):
        require(set(self.licenses) == set(self.expected), "Missing expected license members: " + str(sorted(set(self.expected) - set(self.licenses))))
        for name in self.members:
            parts = name.split("/")
            for index in range(1, len(parts)):
                ancestor = "/".join(parts[:index])
                require(ancestor not in self.members or self.members[ancestor] == "directory", "Member traverses a non-directory/link ancestor: " + name)
        for name, target in self.links.items():
            seen = {name}
            while True:
                pieces = target.split("/")
                link = next(("/".join(pieces[:i]) for i in range(1, len(pieces) + 1)
                             if "/".join(pieces[:i]) in self.links), None)
                if link is None:
                    break
                require(link not in seen and len(seen) < 40, "Cyclic or overlong archive link chain")
                seen.add(link)
                target = self.links[link] + target[len(link):]
        return {"safeMemberPaths": True, "memberCount": len(self.members), "declaredUnpackedBytes": self.total,
                "safeLinksPreserved": len(self.links), "archiveRoot": self.prefix or ".",
                "fullSourceExtractionPerformed": False}


def inspect_archive(entry, path, deadline):
    audit = MemberAudit(entry, deadline)
    if entry["archiveFilename"].endswith(".zip"):
        with zipfile.ZipFile(path) as archive:
            for item in archive.infolist():
                require(not item.flag_bits & 1, "Encrypted source archive member rejected")
                mode = stat.S_IFMT(item.external_attr >> 16)
                require(mode in (0, stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK), "Special ZIP member rejected")
                kind = "directory" if item.is_dir() else "symlink" if mode == stat.S_IFLNK else "file"
                require(not (kind == "directory" and item.file_size), "Directory with payload rejected")
                def read(member=item):
                    with archive.open(member) as stream:
                        data = stream.read(MAX_LICENSE_BYTES + 1)
                    require(len(data) <= MAX_LICENSE_BYTES, "Metadata payload exceeds size limit")
                    return data
                audit.add(item.filename, kind, item.file_size, read)
    else:
        with gzip.open(path, "rb") as decoded:
            bounded = BoundedReader(decoded, deadline)
            with tarfile.open(fileobj=bounded, mode="r|", ignore_zeros=True) as archive:
                for item in archive:
                    require(item.sparse is None, "Sparse source member rejected")
                    if item.isdir():
                        kind = "directory"
                    elif item.isfile():
                        kind = "file"
                    elif item.issym():
                        kind = "symlink"
                    elif item.islnk():
                        kind = "hardlink"
                    else:
                        raise CollectionError("Special tar member rejected: " + item.name)
                    def read(member=item):
                        stream = archive.extractfile(member)
                        require(stream is not None, "Missing regular member payload")
                        with stream:
                            data = stream.read(MAX_LICENSE_BYTES + 1)
                        require(len(data) <= MAX_LICENSE_BYTES, "Metadata payload exceeds size limit")
                        return data
                    audit.add(item.name, kind, item.size, read, item.linkname if kind in ("symlink", "hardlink") else None)
            while bounded.read(CHUNK):
                pass
    return audit.finish(), audit.licenses


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_small_evidence(directory, destination):
    inventory, raw = read_json(directory / "evidence-inventory.json")
    require(inventory.get("schemaVersion") == 1 and inventory.get("root") == "metadata/", "Unsupported evidence inventory")
    records = inventory.get("records")
    require(isinstance(records, list) and 0 < len(records) <= 128, "Unbounded/missing evidence records")
    names, total = set(), 0
    for row in records:
        name = safe_path(row.get("path"))
        require(name not in names, "Duplicate evidence member")
        names.add(name)
        require(type(row.get("bytes")) is int and 0 < row["bytes"] <= MAX_LICENSE_BYTES
                and hex_digest(row.get("sha256"), 64), "Invalid evidence identity")
        total += row["bytes"]
        require(total <= MAX_SMALL_BYTES, "Evidence byte limit exceeded")
        source = directory / "metadata" / name
        require(source.is_file() and not source.is_symlink()
                and source.resolve().is_relative_to((directory / "metadata").resolve()), "Evidence path leaves reviewed directory")
        require(source.stat().st_size == row["bytes"] and file_hash(source) == row["sha256"], "Evidence bytes differ: " + name)
        target = destination / "metadata" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    require(inventory.get("originalTextFiles") == len(records) and inventory.get("originalTextBytes") == total, "Evidence summary differs from records")
    (destination / "evidence-inventory.json").write_bytes(raw)
    return {"included": True, "files": len(records), "bytes": total, "inventorySha256": sha256(raw),
            "scope": "Only exact inventory records; source text is never executed and does not replace source archives."}


def readme_text(count, evidence):
    return f"""# LanType native source WebGPU supplement v1

STATUS: collected bytes awaiting publisher review; not an approved release yet.

This additive source-only package accompanies the unchanged LanType 1.1.0 and
1.1.1 releases. It does not replace any existing three native-source ZIP parts,
application source ZIP, runtime ZIP, APK, release tag or signing certificate.
The exact common APK member is lib/arm64-v8a/libonnxruntime.so, {ELF_BYTES} bytes,
SHA-256 {ELF_SHA256}.

archives/ contains {count} whole original downloads. No source is executed,
patched, configured or compiled. License copies are exact regular members,
checked against the plan's previously inspected license byte/hash metadata.
All source archive paths and link targets were checked without full extraction.
Initial archive SHA-256 values are measured collection results pending review;
the fixed Dawn ZIP is additionally checked against ORT's existing SHA-1 pin.
No timestamp-normalized or alternative Gitiles byte identity is accepted.

Keep the original 70-source attachment parts. reusedSources refers to their
existing ORT and Abseil archives; those bytes are not duplicated or downloaded
by this collector. ORT's seven Dawn patches remain in that original ORT archive.
Their plan identities and order are preserved, not newly applied or presented
as patch-application tests. See installPath and dependsOn for source layout.
omittedOptional preserves the reviewed configuration reasons; this collector
does not crawl all DEPS, execute gclient, or assert the complete vendor build
command is known. The original vendor CMakeCache remains unavailable.

Dawn is already represented in the APK's ORT ThirdPartyNotices. This package
corrects a source-archive coverage omission, not a claim that every Dawn notice
was absent. Every component retains its own license; no blanket GPL relabeling
is made. Only the observed standalone ORT ELF correspondence is established;
the presence of Dawn inside Sherpa's static ORT is not asserted.

Small provenance evidence: {'included and hash-checked' if evidence.get('included') else 'not supplied'}.
The included collection-plan.json is the exact reviewed input; its historical
pending fields are preserved. native-sources-webgpu.lock.json records the actual
collection. Source-derived provenance is not binary-identical rebuild evidence.

Verify using a reviewed repository copy of this script, or the included copy:

    python3 tools/collect-dawn-source-supplement.py --verify /path/to/{ZIP_NAME} --expected-zip-sha256 REVIEWED_ZIP_SHA256

Without an independently reviewed expected ZIP SHA-256, --verify reports internal
consistency only. SOURCE-SHA256SUMS.txt checks every included file except itself.
Do not use the old restore-native-sources.py --all as proof of this supplement;
that command only knows the original source lock. No binary or APK fix, device
acceptance, or full native reproducibility is claimed by this source collection.
"""


def package(stage, output, deadline):
    files = sorted(path for path in stage.rglob("*") if path.is_file())
    require(all(not path.is_symlink() for path in files), "Unexpected generated symlink")
    manifest = "".join(file_hash(path) + "  " + path.relative_to(stage).as_posix() + "\n" for path in files)
    (stage / "SOURCE-SHA256SUMS.txt").write_text(manifest, encoding="utf-8")
    files.append(stage / "SOURCE-SHA256SUMS.txt")
    temporary = output.with_name(output.name + ".partial")
    require(not output.exists() and not temporary.exists(), "Refusing to overwrite supplement ZIP")
    with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path in files:
            deadline.remaining()
            info = zipfile.ZipInfo(NAME + "/" + path.relative_to(stage).as_posix(), (2026, 11, 17, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            with path.open("rb") as source, archive.open(info, "w", force_zip64=True) as target:
                while block := source.read(CHUNK):
                    deadline.remaining()
                    target.write(block)
    temporary.rename(output)


def verify_zip(path, expected=None):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_TOTAL_ARCHIVE_BYTES + 64 * MIB, "Supplement ZIP absent or oversized")
    actual = file_hash(path)
    if expected is not None:
        require(hex_digest(expected, 64) and actual == expected, "Supplement differs from independently supplied ZIP SHA-256")
    prefix = NAME + "/"
    with zipfile.ZipFile(path) as archive:
        entries = {}
        for item in archive.infolist():
            name = safe_path(item.filename)
            require(name.startswith(prefix) and name not in entries and not item.flag_bits & 1
                    and stat.S_IFMT(item.external_attr >> 16) == stat.S_IFREG
                    and item.compress_type == zipfile.ZIP_STORED, "Unexpected/duplicate supplement ZIP member")
            require(item.file_size <= MAX_ARCHIVE_BYTES, "Oversized supplement member")
            entries[name] = item
        require(len(entries) <= MAX_MEMBERS, "Too many supplement members")
        manifest_name = prefix + "SOURCE-SHA256SUMS.txt"
        require(manifest_name in entries and entries[manifest_name].file_size <= MAX_SMALL_BYTES, "Missing/oversized file manifest")
        hashes = {}
        for line in archive.read(manifest_name).decode("utf-8").splitlines():
            require(len(line) > 66 and line[64:66] == "  " and hex_digest(line[:64], 64), "Invalid checksum line")
            name = prefix + safe_path(line[66:])
            require(name not in hashes, "Duplicate checksum entry")
            hashes[name] = line[:64]
        require(set(hashes) == set(entries) - {manifest_name}, "Missing or unexpected supplement members")
        for name, wanted in hashes.items():
            with archive.open(name) as source:
                require(hashlib.file_digest(source, "sha256").hexdigest() == wanted, "Supplement file hash mismatch: " + name)
        lock_name = prefix + "native-sources-webgpu.lock.json"
        require(lock_name in entries and entries[lock_name].file_size <= MAX_SMALL_BYTES, "Missing bounded supplement lock")
        lock = json.loads(archive.read(lock_name), object_pairs_hook=unique_object)
        require(lock.get("binaryEvidence", {}).get("sha256") == ELF_SHA256, "Wrong ORT binary correspondence")
        for row in lock["sources"]:
            name = prefix + "archives/" + safe_path(row["archiveFilename"])
            require(name in entries and entries[name].file_size == row["archiveBytes"]
                    and hashes[name] == row["archiveSha256"], "Archive differs from independent supplement lock")
            for license_row in row["collectedLicenses"]:
                name = prefix + safe_path(license_row["copyPath"])
                require(name in entries and entries[name].file_size == license_row["bytes"]
                        and hashes[name] == license_row["sha256"], "License copy differs from supplement lock")
    return {"status": "verified-against-supplied-zip-sha256" if expected else "internal-consistency-only",
            "file": path.name, "bytes": path.stat().st_size, "sha256": actual, "includedFiles": len(entries)}


def collect(args):
    plan, plan_raw = read_json(args.plan)
    base, base_raw = read_json(ROOT / BASE_LOCK)
    validate_plan(plan, base)
    output = args.output.resolve()
    require(not output.exists(), "Use a fresh output directory; prior evidence/archives are not overwritten")
    output.mkdir(parents=True)
    receipt = {"schemaVersion": 1, "status": "collecting", "planSha256": sha256(plan_raw),
               "baseLockSha256": sha256(base_raw), "nativeCompilationPerformed": False,
               "apkModified": False, "releasePublicationPerformed": False, "sources": []}
    receipt_path = output / "collection-receipt.json"
    write_json(receipt_path, receipt)
    try:
        free = shutil.disk_usage(output).free
        receipt["spacePreflight"] = {"freeBytes": free, "requiredFreeBytes": MIN_FREE_BYTES}
        require(free >= MIN_FREE_BYTES, "Insufficient free disk for bounded source collection and ZIP")
        deadline = Deadline()
        stage = output / NAME
        archives = stage / "archives"
        archives.mkdir(parents=True)
        (stage / "collection-plan.json").write_bytes(plan_raw)
        (stage / "base-native-sources.lock.json").write_bytes(base_raw)
        sources, total = [], 0
        for entry in plan["sources"]:
            print("COLLECT", entry["id"], flush=True)
            path = archives / entry["archiveFilename"]
            measured = download(entry, path, deadline, total)
            total += measured["archiveBytes"]
            audit, licenses = inspect_archive(entry, path, deadline)
            copied = []
            for name, data in sorted(licenses.items()):
                relative = "licenses/" + entry["id"] + "/" + name
                destination = stage / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                copied.append({"sourcePath": name, "copyPath": relative, "bytes": len(data), "sha256": sha256(data)})
            row = dict(entry, **measured, collectionStatus="collected-awaiting-review",
                       memberValidation=audit, collectedLicenses=copied)
            sources.append(row)
            receipt["sources"].append({"id": entry["id"], **measured, "licenses": len(copied), **audit})
            write_json(receipt_path, receipt)
        evidence = {"included": False}
        if args.evidence_dir:
            evidence = copy_small_evidence(args.evidence_dir.resolve(), stage / "provenance-evidence")
        lock = {"schemaVersion": 1, "status": "collected-awaiting-review", "kind": "additive-native-source-only-supplement",
                "reviewRequired": True, "planSha256": sha256(plan_raw), "baseLockSha256": sha256(base_raw),
                "binaryEvidence": plan["binaryEvidence"], "sources": sources,
                "reusedSources": plan["reusedSources"], "omittedOptional": plan["omittedOptional"],
                "ortPatches": plan["ortPatches"], "configurationEvidence": plan.get("configurationEvidence"),
                "sherpaStatic": plan.get("sherpaStatic"), "noticeStatus": plan.get("noticeStatus"),
                "provenanceEvidence": evidence,
                "limits": {"reusedArchiveBytesRedownloaded": False, "ortPatchesApplied": False,
                           "upstreamSourceExecuted": False, "nativeCompilationPerformed": False,
                           "binaryIdenticalReproductionEstablished": False,
                           "initialComputedArchiveHashesArePreviouslyTrustedPins": False}}
        write_json(stage / "native-sources-webgpu.lock.json", lock)
        (stage / "README.md").write_text(readme_text(len(sources), evidence), encoding="utf-8")
        (stage / "tools").mkdir()
        (stage / "tools" / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
        zip_path = output / ZIP_NAME
        package(stage, zip_path, deadline)
        check = verify_zip(zip_path)
        write_json(output / "native-sources-webgpu.lock.json", lock)
        (output / "SUPPLEMENT-SHA256SUMS.txt").write_text(check["sha256"] + "  " + ZIP_NAME + "\n", encoding="utf-8")
        receipt.update(status="collected-awaiting-review", reviewRequired=True, archiveCount=len(sources),
                       totalSourceArchiveBytes=total, provenanceEvidence=evidence, supplement=check)
        write_json(receipt_path, receipt)
        print(json.dumps({"status": receipt["status"], "sources": len(sources), "supplement": check}, ensure_ascii=False), flush=True)
    except Exception as error:
        receipt.update(status="failed", error=type(error).__name__ + ": " + str(error))
        write_json(receipt_path, receipt)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=ROOT / "docs/licensing/dawn-source-plan.json")
    parser.add_argument("--output", type=Path, help="Fresh collector output directory")
    parser.add_argument("--evidence-dir", type=Path, help="Optional reviewed evidence-inventory.json and metadata/ directory")
    parser.add_argument("--verify", type=Path, help="Independently verify a supplement ZIP without downloads")
    parser.add_argument("--expected-zip-sha256", help="Externally reviewed identity for --verify")
    args = parser.parse_args()
    try:
        if args.verify:
            require(not args.output and not args.evidence_dir, "Verification does not collect or copy source files")
            print(json.dumps(verify_zip(args.verify, args.expected_zip_sha256), indent=2))
        else:
            require(args.output is not None and not args.expected_zip_sha256, "Collection requires --output; expected ZIP hash is only for --verify")
            collect(args)
        return 0
    except (CollectionError, OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        print("SOURCE_SUPPLEMENT_FAILED: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
