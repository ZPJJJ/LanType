#!/usr/bin/env python3
"""Fetch fixed or explicitly locked QA APKs from this repository's public releases."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


# Fetch the new public candidate first. If it is not published or does not match,
# stop before a VM starts; never substitute another APK or change permissions.
APKS = (
    {
        "role": "new",
        "name": "LanType-1.1.1-offline-arm64-v8a.apk",
        "url": "https://github.com/ZPJJJ/LanType/releases/download/v1.1.1-rc1/"
               "LanType-1.1.1-offline-arm64-v8a.apk",
        "releaseTag": "v1.1.1-rc1",
        "size": 179987242,
        "sha256": "b841c42366df2db7ef16736ee93a65723e6495aae91dab2e27093db06a40e497",
    },
    {
        "role": "old",
        "name": "LanType-1.1.0-offline-arm64-v8a.apk",
        "url": "https://github.com/ZPJJJ/LanType/releases/download/v1.1.0-rc1/"
               "LanType-1.1.0-offline-arm64-v8a.apk",
        "releaseTag": "v1.1.0-rc1",
        "size": 179983146,
        "sha256": "03e379a9b77fbddba9886e28bfa9fc78e447dc4843917117faf625b4339d18c6",
    },
)
REDIRECTS = {301, 302, 303, 307, 308}
MODES = ("legacy-upgrade", "fresh-candidate", "replace-uninitialized")
PACKAGE = "app.lantype.keyboard"
CERT_SHA256 = "c03b15a19d2ed8899fee6b71f7be09ea5b54c7db9895d7d87b20a9759d8e090b"
BASELINE_1_1_1 = {**APKS[0], "role": "old", "package": PACKAGE,
                  "versionName": "1.1.1", "versionCode": 3,
                  "certificateSha256": CERT_SHA256}
LOCK_FIELDS = {"package", "versionName", "versionCode", "fileName", "size", "sha256",
               "certificateSha256", "url"}


class DownloadError(RuntimeError):
    """A public-safe diagnostic without token-bearing URLs or response bodies."""


def load_candidate_lock(path: Path) -> dict:
    """A missing/invalid explicit lock is an error; there is no latest fallback."""
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise DownloadError("Candidate lock contains a duplicate field")
            result[key] = value
        return result

    try:
        if not path.is_file() or path.stat().st_size > 32768:
            raise DownloadError("Candidate lock must be an existing JSON file no larger than 32 KiB")
        lock = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)
    except (OSError, UnicodeError, ValueError) as error:
        raise DownloadError("Cannot read candidate lock JSON (" + type(error).__name__ + ")") from None
    if not isinstance(lock, dict) or set(lock) != LOCK_FIELDS:
        raise DownloadError("Candidate lock must contain exactly: " + ", ".join(sorted(LOCK_FIELDS)))
    if lock["package"] != PACKAGE or lock["certificateSha256"] != CERT_SHA256:
        raise DownloadError("Candidate lock must name LanType and its established release certificate")
    version = lock["versionName"]
    if not isinstance(version, str) or len(version) > 32 or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
        raise DownloadError("Candidate versionName must be a three-part numeric version")
    if tuple(map(int, version.split("."))) <= (1, 1, 1) or type(lock["versionCode"]) is not int or not 3 < lock["versionCode"] <= 2100000000:
        raise DownloadError("Candidate version must advance beyond fixed baseline 1.1.1/code 3")
    name = "LanType-" + version + "-offline-arm64-v8a.apk"
    if lock["fileName"] != name or type(lock["size"]) is not int or not 0 < lock["size"] <= 512 * 1024**2:
        raise DownloadError("Candidate filename or byte count is invalid")
    if not isinstance(lock["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", lock["sha256"]):
        raise DownloadError("Candidate SHA-256 must contain 64 lowercase hexadecimal characters")
    if not isinstance(lock["url"], str):
        raise DownloadError("Candidate URL must be a fixed public release asset URL")
    prefix = "https://github.com/ZPJJJ/LanType/releases/download/"
    match = re.fullmatch(re.escape(prefix) + r"(v" + re.escape(version) + r"(?:-rc[1-9][0-9]*)?)/" + re.escape(name), lock["url"])
    if not match:
        raise DownloadError("Candidate URL must name this repository's exact versioned release APK, without query or fragment")
    return lock


def candidate_download(lock: dict) -> dict:
    return {"role": "new", "name": lock["fileName"], "url": lock["url"],
            "releaseTag": lock["url"].split("/")[-2],
            **{key: lock[key] for key in ("size", "sha256", "package", "versionName", "versionCode", "certificateSha256")}}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_headers(url: str) -> dict[str, str]:
    try:
        parsed = urllib.parse.urlsplit(url)
        host, port = parsed.hostname or "", parsed.port
    except ValueError:
        raise DownloadError("Refused a malformed download destination") from None
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or port not in (None, 443)
            or not (host == "github.com"
                    or host.endswith(".githubusercontent.com"))):
        raise DownloadError("Refused a non-GitHub HTTPS download destination")
    # Every hop gets a fresh, credential-free request. Do not inherit response
    # headers or use GH_TOKEN/GITHUB_TOKEN, even if present in the environment.
    return {"Accept": "application/octet-stream", "User-Agent": "LanType-device-QA"}


def open_binary(url: str):
    opener = urllib.request.build_opener(NoRedirect())
    for _ in range(6):
        request = urllib.request.Request(url, headers=request_headers(url))
        try:
            return opener.open(request, timeout=60)
        except urllib.error.HTTPError as error:
            status = error.code
            location = error.headers.get("Location")
            error.close()
            if status in REDIRECTS and location:
                url = urllib.parse.urljoin(url, location)
                continue
            if status in (401, 403, 404):
                raise DownloadError(
                    f"Public release download HTTP {status}: the fixed APK is not publicly accessible. "
                    "This download prerequisite failed before VM or product execution."
                ) from None
            raise DownloadError(f"Download server returned HTTP {status}") from None
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as error:
            # Exception messages may contain an expiring signed redirect URL.
            raise DownloadError(f"Download connection failed ({type(error).__name__})") from None
    raise DownloadError("Too many download redirects")


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch(apk: dict, output: Path) -> dict:
    destination = output / apk["name"]
    cached = destination.exists()
    if cached:
        if destination.stat().st_size != apk["size"] or file_sha256(destination) != apk["sha256"]:
            raise DownloadError(f"Existing {apk['name']} does not match the fixed QA input")
    else:
        temporary = destination.with_suffix(".apk.part")
        digest = hashlib.sha256()
        size = 0
        try:
            with open_binary(apk["url"]) as response, temporary.open("wb") as target:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > apk["size"]:
                        raise DownloadError(f"{apk['name']} exceeds the fixed byte count")
                    digest.update(chunk)
                    target.write(chunk)
            if size != apk["size"] or digest.hexdigest() != apk["sha256"]:
                raise DownloadError(f"{apk['name']} failed exact size/SHA-256 verification")
            temporary.replace(destination)
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as error:
            raise DownloadError(f"Download or local write failed ({type(error).__name__})") from None
        finally:
            temporary.unlink(missing_ok=True)
    return {**{key: value for key, value in apk.items() if key != "url"},
            "verified": True, "reusedVerifiedFile": cached}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Disposable APK directory")
    parser.add_argument("--receipt", type=Path, required=True, help="Small public-safe JSON evidence")
    parser.add_argument("--mode", choices=MODES, default="legacy-upgrade")
    parser.add_argument("--candidate-lock", type=Path, help="Required fixed signed-candidate identity for either new mode")
    args = parser.parse_args()
    lock = None
    if args.mode != "legacy-upgrade" and args.candidate_lock is None:
        parser.error("--candidate-lock is required for " + args.mode + "; no latest APK is selected")
    if args.mode == "legacy-upgrade" and args.candidate_lock is not None:
        parser.error("--candidate-lock is not used by the unchanged legacy-upgrade inputs")
    if args.candidate_lock is not None:
        try:
            lock = load_candidate_lock(args.candidate_lock)
        except DownloadError as error:
            parser.error(str(error))
    selected = APKS if lock is None else [candidate_download(lock)]
    if args.mode == "replace-uninitialized":
        selected.append(BASELINE_1_1_1)
    args.output.mkdir(parents=True, exist_ok=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt = {"schemaVersion": 1, "checkedAtUtc": datetime.now(timezone.utc).isoformat(),
               "status": "running", "downloads": []}
    if lock is not None:
        receipt.update(mode=args.mode, candidateLockSha256=file_sha256(args.candidate_lock),
                       verificationScope="Exact download size and SHA-256; signature is checked by the device driver")
    try:
        for apk in selected:
            receipt["downloads"].append(fetch(apk, args.output))
            print(f"Verified {apk['name']}: {apk['size']} bytes, SHA-256 {apk['sha256']}")
        receipt["status"] = "passed"
        return 0
    except (DownloadError, OSError) as error:
        diagnostic = str(error) if isinstance(error, DownloadError) else type(error).__name__
        receipt.update(status="blocked", error=diagnostic)
        print(diagnostic, file=sys.stderr)
        return 1
    finally:
        args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
