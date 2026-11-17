#!/usr/bin/env python3
"""Check the staged/tracked public source inventory without printing secrets."""
from pathlib import Path
import argparse
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_GIT_BLOB = 100 * 1024 * 1024
ALLOWED_WORKFLOWS = {
    ".github/workflows/offline-ci.yml",
    ".github/workflows/android-device-qa.yml",
    # Reviewed read-only source collection and bounded native build workflows.
    # Neither publishes a release, signs an APK, nor receives private keys.
    ".github/workflows/native-source-supplement.yml",
    ".github/workflows/native-ort-build.yml",
}
DENIED_PARTS = {".gradle", ".cxx", "node_modules", "private-signing", "recovery", "deliverables"}
DENIED_SUFFIXES = {".jks", ".keystore", ".p12", ".pfx", ".key", ".pem", ".apk", ".aab", ".so", ".onnx", ".tflite", ".hprof", ".xipk"}
DENIED_PREFIXES = ("vendor/", "toolchain/", "scripts/packager/", "tools/ime_lab/fixtures/",
                   "tools/demo_typer/", "tools/speech_lab/", "docs/validation/", "app/build/", "plugin-core/build/",
                   "app/src/androidTest/assets/ocr/",
                   "docs/releases/evidence/", "app/src/androidTest/assets/ime_lab/")
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
)


def tracked_files():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
    return sorted(set(result.stdout.decode().split("\0")) - {""})


def inspect(paths):
    findings = []
    for relative in paths:
        path = ROOT / relative
        low = relative.lower()
        if (any(part in DENIED_PARTS for part in Path(relative).parts)
                or low.startswith(DENIED_PREFIXES) or path.suffix.lower() in DENIED_SUFFIXES
                or path.name in {"local.properties", "keystore.properties", "AGENTS.local.md"}
                or "signing-backup" in low or "signing-password" in low):
            findings.append((relative, "private/generated/binary path is not public source"))
            continue
        if not path.is_file() or path.is_symlink():
            findings.append((relative, "missing file or symlink requires explicit review"))
            continue
        if path.stat().st_size > MAX_GIT_BLOB:
            findings.append((relative, "exceeds GitHub's 100 MiB per-file limit"))
            continue
        if path.stat().st_size < 5 * 1024 * 1024:
            data = path.read_bytes()
            if any(pattern.search(data) for pattern in SECRET_PATTERNS):
                findings.append((relative, "possible private key or access token; value suppressed"))
        if relative.startswith(".github/workflows/") and relative not in ALLOWED_WORKFLOWS:
            findings.append((relative, "workflow has not been reviewed for LanType"))
    return findings


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    paths = tracked_files()
    if not paths:
        raise SystemExit("No tracked source files: stage the reviewed source inventory first.")
    findings = inspect(paths)
    for path, reason in findings:
        print(f"REJECT {path}: {reason}")
    if findings:
        raise SystemExit(1)
    print(f"PUBLIC_SOURCE_CHECK_PASSED: {len(paths)} tracked files; no forbidden paths, oversized blobs or high-confidence secret patterns.")


if __name__ == "__main__":
    main()
