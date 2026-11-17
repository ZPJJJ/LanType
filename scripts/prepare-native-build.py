#!/usr/bin/env python3
"""Prepare pinned ORT headers/shared libraries for the optional JNI source build."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true',
                        help='Retained for command compatibility; prepare the accepted ORT runtime separately.')
    parser.parse_args()
    lock_path = ROOT / 'docs/licensing/ort-runtime.lock.json'
    verify = [sys.executable, str(ROOT / 'scripts/prepare-ort-runtime.py'),
              '--accepted-lock', str(lock_path)]
    subprocess.run([*verify, '--verify-only'], cwd=ROOT, check=True)
    lock = json.loads(lock_path.read_text())
    source = ROOT / 'vendor/native-sources/runtime-onnxruntime/include/onnxruntime'
    if not (source / 'core/session/onnxruntime_c_api.h').is_file():
        raise SystemExit('First restore the locked JNI source prerequisites with scripts/restore-native-sources.py.')
    cpp = ROOT / 'app/src/main/jni/onnxruntime'
    headers = cpp / 'include'
    headers.mkdir(parents=True, exist_ok=True)
    for header in (source / 'core/session').iterdir():
        if header.is_file() and header.suffix in ('.h', '.inc'):
            shutil.copyfile(header, headers / header.name)
    for relative in ('core/providers/nnapi/nnapi_provider_factory.h', 'core/providers/cpu/cpu_provider_factory.h'):
        shutil.copyfile(source / relative, headers / Path(relative).name)
    target = cpp / 'lib/arm64-v8a/libonnxruntime.so'
    target.parent.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / 'vendor/ort-runtime/arm64-v8a/libonnxruntime.so'
    # Replace the directory entry, never mutate a shared hard-linked runtime.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='ort-', suffix='.tmp', dir=target.parent, delete=False) as output:
            temporary = Path(output.name)
            with runtime.open('rb') as stream:
                shutil.copyfileobj(stream, output)
        if temporary.stat().st_size != lock['library']['bytes'] or digest(temporary) != lock['library']['sha256']:
            raise SystemExit('Accepted ORT runtime changed while copying.')
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    subprocess.run([*verify, '--verify-native-input', str(target)], cwd=ROOT, check=True)
    print('NATIVE_BUILD_INPUTS_READY: exact ORT 1.28.0 headers and accepted ARM64 replacement')


if __name__ == '__main__':
    main()
