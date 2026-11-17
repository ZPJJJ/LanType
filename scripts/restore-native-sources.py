#!/usr/bin/env python3
"""Verify/materialize actual pinned native source archives; never restore app assets.
Use the release source attachment with --archive-dir, or --download for development.
"""
from pathlib import Path, PurePosixPath
import argparse
import gzip
import hashlib
import io
import json
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'docs/licensing/native-sources.lock.json'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def filter_upstream(data):
    """Preserve original native wrappers/build scripts, omitting all upstream assets."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as source:
        selected = []
        for member in source.getmembers():
            relative = '/'.join(PurePosixPath(member.name).parts[1:])
            allowed = relative.startswith(('app/src/main/jni/', 'app/build-logic/', 'patches/', 'gradle/')) or relative in (
                'app/build.gradle.kts', 'build.gradle.kts', 'settings.gradle.kts', 'gradle.properties',
                'LICENSE', '.gitmodules', 'gradlew', 'gradlew.bat')
            if member.isfile() and allowed:
                selected.append((relative, member))
        with tarfile.open(fileobj=buffer, mode='w', format=tarfile.PAX_FORMAT) as dest:
            for relative, member in sorted(selected):
                content = source.extractfile(member).read()
                item = tarfile.TarInfo('cyime-native-build-source/' + relative)
                item.size, item.mode, item.mtime = len(content), member.mode, 0
                dest.addfile(item, io.BytesIO(content))
    compressed = bytearray(gzip.compress(buffer.getvalue(), compresslevel=6, mtime=0))
    compressed[9] = 255
    return bytes(compressed)


def obtain(entry, cache, download):
    path = cache / entry['archive_file']
    if path.is_file() and digest(path) == entry['archive_sha256']:
        return path
    if not download:
        raise SystemExit(f'Missing/changed source archive: {path}. Supply the source attachment or --download.')
    cache.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.partial')
    with urllib.request.urlopen(entry['archive_url'], timeout=240) as response, temporary.open('wb') as target:
        shutil.copyfileobj(response, target)
    if entry.get('filtered'):
        if digest(temporary) != entry['original_archive_sha256']:
            raise SystemExit('Original upstream source archive hash differs from the reviewed source.')
        temporary.write_bytes(filter_upstream(temporary.read_bytes()))
    if digest(temporary) != entry['archive_sha256']:
        raise SystemExit(f"Source archive hash mismatch: {entry['id']}")
    temporary.replace(path)
    return path


def extract(entry, archive):
    relative = PurePosixPath(entry['installPath'])
    if relative.is_absolute() or '..' in relative.parts or 'assets' in relative.parts:
        raise SystemExit('Native source lock contains a forbidden destination.')
    destination = ROOT / relative
    marker = destination / '.lantype-source-sha256'
    if marker.is_file() and marker.read_text().strip() == entry['archive_sha256']:
        return
    if destination.exists() and any(path.is_file() for path in destination.rglob('*')):
        raise SystemExit(f'Preserving nonempty source tree {relative}; move it aside explicitly before restoration.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        temp = Path(temporary)
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as source:
                for item in source.infolist():
                    name = PurePosixPath(item.filename)
                    if name.is_absolute() or '..' in name.parts:
                        raise SystemExit('Unsafe ZIP member in source archive.')
                    if (item.external_attr >> 16) & 0o170000 == 0o120000:
                        raise SystemExit('Symlink ZIP member requires manual source review.')
                source.extractall(temp)
        else:
            with tarfile.open(archive) as source:
                source.extractall(temp, filter='data')
        children = list(temp.iterdir())
        if not entry.get('flatRoot') and (len(children) != 1 or not children[0].is_dir()):
            raise SystemExit(f'Unexpected source archive root: {archive.name}')
        shutil.copytree(temp if entry.get('flatRoot') else children[0], destination, dirs_exist_ok=True)
    marker.write_text(entry['archive_sha256'] + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-dir', type=Path, default=ROOT / '.gradle/native-source-archives')
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--all', action='store_true', help='Also restore runtime and static dependency source trees')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    lock = json.loads(LOCK.read_text())
    selected = [entry for entry in lock['sources'] if args.all or entry['group'] == 'rime' or entry['id'] in ('runtime-boost', 'runtime-onnxruntime')]
    for entry in sorted(selected, key=lambda item: len(PurePosixPath(item['installPath']).parts)):
        archive = obtain(entry, args.archive_dir, args.download)
        if not args.verify_only:
            extract(entry, archive)
        print('SOURCE_VERIFIED', entry['id'])
    print(f'NATIVE_SOURCE_VERIFICATION_PASSED: {len(selected)} actual source archives')


if __name__ == '__main__':
    main()
