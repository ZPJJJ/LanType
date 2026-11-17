#!/usr/bin/env python3
"""Prepare pinned ORT headers/shared libraries for the optional JNI source build."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'docs/licensing/native-sources.lock.json').read_text())
    source = ROOT / 'vendor/native-sources/runtime-onnxruntime/include/onnxruntime'
    if not (source / 'core/session/onnxruntime_c_api.h').is_file():
        raise SystemExit('First restore the locked JNI source prerequisites with scripts/restore-native-sources.py.')
    entry = lock['onnxAndroidAar']
    cache = ROOT / '.gradle/native-source-archives'
    cache.mkdir(parents=True, exist_ok=True)
    aar = cache / 'onnxruntime-android-1.28.0.aar'
    if not aar.is_file() or digest(aar) != entry['sha256']:
        gradle_cache = Path(os.environ.get('GRADLE_USER_HOME', Path.home() / '.gradle')) / 'caches/modules-2/files-2.1/com.microsoft.onnxruntime/onnxruntime-android/1.28.0'
        match = next((p for p in gradle_cache.glob('*/*.aar') if digest(p) == entry['sha256']), None)
        if match:
            shutil.copyfile(match, aar)
        elif args.download:
            with urllib.request.urlopen(entry['url'], timeout=240) as response, aar.open('wb') as target:
                shutil.copyfileobj(response, target)
        else:
            raise SystemExit('Locked ORT Android AAR not cached; use --download for development-time preparation.')
    if digest(aar) != entry['sha256']:
        raise SystemExit('ORT AAR checksum mismatch.')
    cpp = ROOT / 'app/src/main/jni/onnxruntime'
    headers = cpp / 'include'
    headers.mkdir(parents=True, exist_ok=True)
    for header in (source / 'core/session').iterdir():
        if header.is_file() and header.suffix in ('.h', '.inc'):
            shutil.copyfile(header, headers / header.name)
    for relative in ('core/providers/nnapi/nnapi_provider_factory.h', 'core/providers/cpu/cpu_provider_factory.h'):
        shutil.copyfile(source / relative, headers / Path(relative).name)
    with zipfile.ZipFile(aar) as archive:
        target = cpp / 'lib/arm64-v8a/libonnxruntime.so'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read('jni/arm64-v8a/libonnxruntime.so'))
    print('NATIVE_BUILD_INPUTS_READY: exact ORT 1.28.0 headers and verified ARM64 shared runtime')


if __name__ == '__main__':
    main()
