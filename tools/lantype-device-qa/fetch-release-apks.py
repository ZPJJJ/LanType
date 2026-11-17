#!/usr/bin/env python3
"""Fetch the two fixed, signed QA APKs; never forward API credentials on redirects."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request


# Test the draft first: a read-only token may not see it. Do not silently publish
# the release, change permissions, or substitute an unsigned build on failure.
APKS = (
    {
        "role": "new",
        "name": "LanType-1.1.1-offline-arm64-v8a.apk",
        "url": "https://api.github.com/repos/ZPJJJ/LanType/releases/assets/759263281",
        "releaseId": 448699588,
        "assetId": 759263281,
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


class DownloadError(RuntimeError):
    """A public-safe diagnostic without token-bearing URLs or response bodies."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_headers(url: str, token: str) -> dict[str, str]:
    try:
        parsed = urllib.parse.urlsplit(url)
        host, port = parsed.hostname or "", parsed.port
    except ValueError:
        raise DownloadError("Refused a malformed download destination") from None
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or port not in (None, 443)
            or not (host in {"github.com", "api.github.com"}
                    or host.endswith(".githubusercontent.com"))):
        raise DownloadError("Refused a non-GitHub HTTPS download destination")
    headers = {"Accept": "application/octet-stream", "User-Agent": "LanType-device-QA"}
    # A new header dictionary is created for EVERY hop. urllib's normal redirect
    # handling can carry custom Authorization headers to another origin.
    if host == "api.github.com":
        headers["X-GitHub-Api-Version"] = "2026-03-10"
        if token:
            headers["Authorization"] = "Bearer " + token
    return headers


def open_binary(url: str, token: str):
    opener = urllib.request.build_opener(NoRedirect())
    for _ in range(6):
        request = urllib.request.Request(url, headers=request_headers(url, token))
        try:
            return opener.open(request, timeout=60)
        except urllib.error.HTTPError as error:
            status = error.code
            location = error.headers.get("Location")
            error.close()
            if status in REDIRECTS and location:
                url = urllib.parse.urljoin(url, location)
                continue
            if urllib.parse.urlsplit(url).hostname == "api.github.com" and status in (401, 403, 404):
                raise DownloadError(
                    f"GitHub API HTTP {status}: the fixed draft asset is not accessible with this token. "
                    "contents:read does not guarantee draft visibility; permissions remain unchanged."
                ) from None
            raise DownloadError(f"Download server returned HTTP {status}") from None
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as error:
            # Exception messages may contain an expiring signed redirect URL.
            raise DownloadError(f"Download connection failed ({type(error).__name__})") from None
    raise DownloadError("Too many download redirects")


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch(apk: dict, output: Path, token: str) -> dict:
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
            with open_binary(apk["url"], token) as response, temporary.open("wb") as target:
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
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt = {"schemaVersion": 1, "checkedAtUtc": datetime.now(timezone.utc).isoformat(),
               "status": "running", "downloads": []}
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    try:
        for apk in APKS:
            receipt["downloads"].append(fetch(apk, args.output, token))
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
