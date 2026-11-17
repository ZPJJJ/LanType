#!/usr/bin/env python3
"""Materialize only checksum-locked native libraries and the Sherpa Java API.

No upstream Java/Kotlin DEX is reused. LanType's application classes are compiled
from the matching GPL source. --apk and --speech-aar support an offline rebuild.
Upstream APK assets are never copied: commercial-edition data has a separate
reviewed resource lock and preparation workflow.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.15.94"
APK_NAME = f"CyIME-{VERSION}-full-arm64-v8a.apk"
APK_SHA = "d121abd5345b6f02202803ba10b9368c39a84e49f549143199f5edd38ca19e86"
SPEECH_NAME = "sherpa-onnx-static-link-onnxruntime-1.13.8.aar"
SPEECH_SHA = "b22c3fc1b6a45666d28892bb2f7694beeb77a8362d7ebd77c1a5431ec9435471"
APK_URL = f"https://github.com/Cyletix/CyIME/releases/download/{VERSION}/{APK_NAME}"
SPEECH_URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.8/{SPEECH_NAME}"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            value.update(block)
    return value.hexdigest()


def obtain(path, url, expected):
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".download")
        with urllib.request.urlopen(url, timeout=60) as source, temporary.open("wb") as dest:
            shutil.copyfileobj(source, dest)
        if digest(temporary) != expected:
            temporary.unlink()
            raise SystemExit(f"SHA-256 mismatch: {url}")
        temporary.replace(path)
    if digest(path) != expected:
        raise SystemExit(f"SHA-256 mismatch: {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path)
    parser.add_argument("--speech-aar", type=Path)
    parser.add_argument("--verify-only", action="store_true", help="Check local locked native files without downloading")
    options = parser.parse_args()
    target = ROOT / "vendor" / f"cyime-{VERSION}"
    lock = json.loads((ROOT / "docs/licensing/native-prebuilt.lock.json").read_text())
    invalid = [entry["path"] for entry in lock["files"] if not (target / entry["path"]).is_file()
               or (target / entry["path"]).stat().st_size != entry["size"]
               or digest(target / entry["path"]) != entry["sha256"]]
    if not invalid:
        print(f"Verified {len(lock['files'])} local native/API files; no download needed.")
        return
    if options.verify_only:
        raise SystemExit("Missing or altered native files: " + ", ".join(invalid))
    cache = ROOT / ".gradle" / "upstream-downloads"
    apk = obtain(options.apk or cache / APK_NAME, APK_URL, APK_SHA)
    aar = obtain(options.speech_aar or cache / SPEECH_NAME, SPEECH_URL, SPEECH_SHA)
    archives = {"apk": apk, "speechAar": aar}
    for entry in lock["files"]:
        relative = entry["path"]
        if not relative.startswith(("jniLibs/arm64-v8a/", "java/")) or ".." in Path(relative).parts:
            raise SystemExit(f"Refusing non-native bootstrap path: {relative}")
        with zipfile.ZipFile(archives[entry["sourceArchive"]]) as archive:
            content = archive.read(entry["archivePath"])
        if len(content) != entry["size"] or hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise SystemExit(f"Locked native payload mismatch: {relative}")
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".new")
        temporary.write_bytes(content)
        temporary.replace(path)
    print(f"Verified and prepared {len(lock['files'])} locked native/API files; no APK assets extracted.")


if __name__ == "__main__":
    main()
