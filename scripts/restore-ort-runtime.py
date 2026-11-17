#!/usr/bin/env python3
"""Restore the three accepted ORT outputs from a pinned public component release.

Downloads require --download. No lock is changed and no native code is executed.
Extra README/license/evidence members are checked but never extracted.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("ort_runtime", Path(__file__).with_name("prepare-ort-runtime.py"))
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)
LOCK = runtime.ROOT / "docs/licensing/ort-runtime.lock.json"
CACHE = runtime.ROOT / ".gradle/ort-runtime-archives"
RELEASE_PATH = r"/ZPJJJ/LanType/releases/download/[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*\.zip"


def distribution(lock):
    entry = lock.get("distribution")
    runtime.require(isinstance(entry, dict), "Accepted lock has no distribution entry")
    url, root = entry.get("archiveUrl"), entry.get("root")
    runtime.require(isinstance(url, str) and not any(ord(char) <= 32 or ord(char) == 127 for char in url),
                    "Invalid component archive URL")
    parsed = urlsplit(url)
    runtime.require(parsed.scheme == "https" and parsed.netloc == "github.com"
                    and "?" not in url and "#" not in url
                    and re.fullmatch(RELEASE_PATH, parsed.path),
                    "Archive URL must be a plain HTTPS release ZIP from ZPJJJ/LanType")
    runtime.require(isinstance(root, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", root),
                    "Invalid component archive root")
    archive = runtime.identity(entry.get("archive"), "distribution.archive")
    runtime.require(0 < archive["bytes"] <= 2 * runtime.GIB, "Component archive exceeds the 2 GiB limit")
    return url, root, archive


class ReleaseRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        parsed = urlsplit(new_url)
        runtime.require(parsed.scheme == "https" and not parsed.fragment and parsed.netloc in (
            "github.com", "release-assets.githubusercontent.com"), "Unexpected release download redirect")
        if parsed.netloc == "github.com":
            runtime.require(re.fullmatch(RELEASE_PATH, parsed.path) and "?" not in new_url,
                            "Redirect left the pinned repository release")
        else:
            runtime.require(parsed.path.startswith("/github-production-release-asset/")
                            and all(part not in ("", ".", "..") for part in parsed.path[1:].split("/"))
                            and "%" not in parsed.path and "\\" not in parsed.path,
                            "Unexpected GitHub release asset path")
        return super().redirect_request(request, response, code, message, headers, new_url)


def check_archive(path, expected):
    runtime.require(path.is_file() and not path.is_symlink() and path.stat().st_size == expected["bytes"],
                    f"Component ZIP is missing or has the wrong size: {path}")
    runtime.match(runtime.file_identity(path), expected, "component archive")


def obtain(url, expected, archive, download):
    if archive is not None:
        check_archive(archive, expected)
        return archive
    path = CACHE / (expected["sha256"] + ".zip")
    if path.exists() or path.is_symlink():
        check_archive(path, expected)
        return path
    runtime.require(download, "No cached runtime ZIP; provide --archive FILE or explicitly allow --download")
    CACHE.mkdir(parents=True, exist_ok=True)
    runtime.require(shutil.disk_usage(CACHE).free >= expected["bytes"] + 5 * runtime.GIB,
                    "Insufficient space for the download and a 5 GiB reserve")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix="ort-", suffix=".tmp", dir=CACHE, delete=False) as output:
            temporary = Path(output.name)
            request = Request(url, headers={"User-Agent": "LanType-ORT-restorer", "Accept-Encoding": "identity"})
            with build_opener(ReleaseRedirect()).open(request, timeout=60) as response:
                total = 0
                while chunk := response.read(min(runtime.CHUNK, expected["bytes"] - total + 1)):
                    total += len(chunk)
                    runtime.require(total <= expected["bytes"], "Download exceeds the locked byte count")
                    output.write(chunk)
        check_archive(temporary, expected)
        runtime.require(not path.exists() and not path.is_symlink(), "Cache entry appeared during download")
        temporary.rename(path)
        return path
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def restore(lock, directory, archive=None, download=False):
    if directory.exists() or directory.is_symlink():
        return {"alreadyPresent": True, **runtime.verify_bundle(directory, lock)}
    url, root, expected = distribution(lock)
    output_bytes = sum(runtime.identity(value, name)["bytes"] for name, value in lock["outputs"].items())
    runtime.require(output_bytes + expected["bytes"] < 5 * runtime.GIB, "Restoration exceeds the 5 GiB temporary-data budget")
    archive = obtain(url, expected, archive, download)
    with zipfile.ZipFile(archive) as source:
        index = runtime.archive_index(source)
        runtime.require(all(name.startswith(root + "/") for name in index), "ZIP member outside the locked root")
        for name, relative in runtime.OUTPUTS.items():
            member = index.get(root + "/" + relative)
            runtime.require(member is not None and not member.is_dir()
                            and member.file_size == lock["outputs"][name]["bytes"],
                            f"Missing or incorrectly sized runtime ZIP member: {relative}")
        directory.parent.mkdir(parents=True, exist_ok=True)
        runtime.require(shutil.disk_usage(directory.parent).free >= output_bytes + 5 * runtime.GIB,
                        "Insufficient space for restored outputs and a 5 GiB reserve")
        staging = Path(tempfile.mkdtemp(prefix=".ort-restore-", dir=directory.parent))
        try:
            for name, relative in runtime.OUTPUTS.items():
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(index[root + "/" + relative]) as incoming, target.open("xb") as outgoing:
                    runtime.match(runtime.stream_identity(incoming, [outgoing]), lock["outputs"][name], relative)
            result = runtime.verify_bundle(staging, lock)
            check_archive(archive, expected)
            runtime.require(not directory.exists() and not directory.is_symlink(), "Output appeared during restoration; kept it unchanged")
            staging.rename(directory)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    return {"alreadyPresent": False, "archive": expected, **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=LOCK, help="Accepted runtime lock (default: docs/licensing/ort-runtime.lock.json)")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--archive", type=Path, help="Local pinned runtime ZIP; no network access")
    inputs.add_argument("--download", action="store_true", help="Explicitly allow downloading the pinned public release ZIP")
    parser.add_argument("--output-dir", type=Path, default=runtime.DEFAULT_OUTPUT, help="Default: vendor/ort-runtime")
    args = parser.parse_args()
    lock, digest = runtime.load_lock(args.lock, accepted=True)
    result = restore(lock, args.output_dir, args.archive, args.download)
    print(json.dumps({"ok": True, "kind": "lantype-ort-runtime-restore-receipt", "lockSha256": digest,
                      "outputDirectory": str(args.output_dir.resolve()), "nativeCodeExecuted": False,
                      "runtimeAcceptancePerformed": False, **result}, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, zipfile.BadZipFile, EOFError, KeyError, TypeError) as error:
        print(json.dumps({"ok": False, "error": str(error), "nativeCodeExecuted": False}), file=sys.stderr)
        sys.exit(1)
