#!/usr/bin/env python3
"""Create source and approved runtime ZIPs from explicit reviewed inventories.

The app source ZIP uses git ls-files, never a recursive working-directory dump.
The runtime ZIP uses only resource and native locks, never vendor/ wholesale.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION_MATCH = re.search(r'versionName\s*=\s*"(\d+\.\d+\.\d+)"', (ROOT / 'app/build.gradle.kts').read_text())
if VERSION_MATCH is None:
    raise SystemExit('Cannot determine the release version from app/build.gradle.kts')
VERSION = VERSION_MATCH.group(1)
PREFIX = f'LanType-{VERSION}/'


def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_zip(output, paths, kind):
    output.parent.mkdir(parents=True, exist_ok=True)
    inventory = []
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for relative in sorted(set(paths)):
            source = ROOT / relative
            if not source.is_file() or source.is_symlink():
                raise SystemExit(f'Non-regular source path rejected: {relative}')
            entry = {'path': relative, 'size': source.stat().st_size, 'sha256': digest(source)}
            inventory.append(entry)
            info = zipfile.ZipInfo(PREFIX + relative, (2026, 11, 17, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if os.access(source, os.X_OK) else 0o100644) << 16
            with source.open('rb') as stream, archive.open(info, 'w', force_zip64=True) as target:
                while chunk := stream.read(1024 * 1024):
                    target.write(chunk)
        manifest = {'edition': VERSION, 'kind': kind, 'files': inventory}
        info = zipfile.ZipInfo(PREFIX + kind.upper() + '-INVENTORY.json', (2026, 11, 17, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    receipt = {'file': output.name, 'kind': kind, 'size': output.stat().st_size, 'sha256': digest(output), 'includedFiles': len(inventory)}
    output.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-output', type=Path, required=True)
    runtime = parser.add_mutually_exclusive_group(required=True)
    runtime.add_argument('--runtime-output', type=Path)
    runtime.add_argument('--source-only', action='store_true',
                         help='Package application source only; provide the unchanged runtime and native source archives separately.')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    public = load_module('public_inventory', 'check-public-source.py')
    source_files = public.tracked_files()
    if subprocess.run(['git', 'diff', '--quiet', '--'], cwd=ROOT).returncode:
        raise SystemExit('Tracked working files differ from the reviewed Git index; stage the intended final bytes before packaging.')
    if not source_files:
        raise SystemExit('No reviewed Git inventory. Stage the intended public source first.')
    findings = public.inspect(source_files)
    if findings:
        for path, reason in findings:
            print(f'REJECT {path}: {reason}')
        raise SystemExit(1)
    resources = load_module('resources', 'verify-commercial-resources.py')
    report = resources.check()
    if not report['pass']:
        raise SystemExit('Resource whitelist verification failed; run scripts/verify-commercial-resources.py for details.')
    lock = json.loads((ROOT / 'docs/licensing/resources.lock.json').read_text())
    runtime_files = ['app/src/main/assets/' + entry['path'] for entry in lock['resources']]
    runtime_files += [str(resources.raw_path(entry).relative_to(ROOT)) for entry in lock.get('rawResources', [])]
    native = json.loads((ROOT / 'docs/licensing/native-prebuilt.lock.json').read_text())
    for entry in native['files']:
        path = ROOT / 'vendor/cyime-1.15.94' / entry['path']
        if not path.is_file() or path.stat().st_size != entry['size'] or digest(path) != entry['sha256']:
            raise SystemExit(f"Native dependency differs from lock: {entry['path']}")
        runtime_files.append(str(path.relative_to(ROOT)))
    runtime_files += ['LICENSE', 'NOTICE', 'docs/licensing/resources.lock.json', 'docs/licensing/native-prebuilt.lock.json']
    camera_lock = json.loads((ROOT / 'docs/licensing/camerax-rebuilt.lock.json').read_text())
    for entry in camera_lock['outputs']:
        path = ROOT / entry['path']
        if not path.is_file() or path.stat().st_size != entry['size'] or digest(path) != entry['sha256']:
            raise SystemExit('Rebuilt CameraX dependency differs from its lock: ' + entry['path'])
        runtime_files.append(entry['path'])
    runtime_files.append('docs/licensing/camerax-rebuilt.lock.json')
    runtime_files = [path for path in runtime_files if (ROOT / path).is_file()]
    if args.dry_run:
        print(json.dumps({'sourceFiles': len(source_files), 'runtimeFiles': len(set(runtime_files)),
                          'sourceBytes': sum((ROOT / path).stat().st_size for path in source_files),
                          'runtimeBytes': sum((ROOT / path).stat().st_size for path in set(runtime_files))}, indent=2))
        return
    write_zip(args.source_output, source_files, 'source')
    if args.runtime_output:
        write_zip(args.runtime_output, runtime_files, 'runtime-dependencies')


if __name__ == '__main__':
    main()
