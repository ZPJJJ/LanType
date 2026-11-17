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
import re
import shutil
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'docs/licensing/native-sources.lock.json'
GITILES_CONTENT_FORMAT = 'gitiles-tar-members-v1'


class SourceArchiveMismatch(ValueError):
    """A downloaded archive does not match either approved source identity."""


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def is_pinned_gitiles(entry):
    """Content verification is opt-in and restricted to exact Gitiles commits."""
    url = urllib.parse.urlsplit(entry.get('archive_url', ''))
    commit = entry.get('commit', '')
    return (url.scheme == 'https' and url.netloc == 'android.googlesource.com'
            and not url.query and not url.fragment and not entry.get('filtered')
            and re.fullmatch(r'[0-9a-f]{40}', commit) is not None
            and re.fullmatch(r'/[^?]+/\+archive/' + re.escape(commit)
                             + r'(?:/[^?]+)?\.tar\.gz', url.path) is not None)


def gitiles_content_identity(path, limits=None):
    """Hash exact tar member identities, excluding only modification timestamps.

    Gitiles regenerates tar/PAX mtime values on download. Container headers and
    compressed bytes therefore are not a stable content identity. The canonical
    record includes every member path, type, mode, owner, link, size, device
    number, all non-mtime PAX fields and each regular file's SHA-256. Paths are
    not normalized or merged. Duplicate paths and sparse/special files fail.
    """
    records, seen, file_count, file_bytes = [], set(), 0, 0
    try:
        with tarfile.open(path, mode='r|gz') as archive:
            for member in archive:
                name = member.name
                parts = PurePosixPath(name)
                if (not name or '\x00' in name or parts.is_absolute()
                        or '..' in parts.parts or name in seen):
                    raise SourceArchiveMismatch('Unsafe or duplicate Gitiles member: ' + name)
                seen.add(name)
                if limits and len(seen) > limits['memberCount']:
                    raise SourceArchiveMismatch('Gitiles archive contains added members.')
                if (member.sparse is not None or not (member.isfile() or member.isdir()
                        or member.issym() or member.islnk()) or member.size < 0):
                    raise SourceArchiveMismatch('Unsupported Gitiles member type: ' + name)
                payload_hash = None
                if member.isfile():
                    file_count += 1
                    file_bytes += member.size
                    if limits and file_bytes > limits['regularFileBytes']:
                        raise SourceArchiveMismatch('Gitiles source payload exceeds the approved size.')
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise SourceArchiveMismatch('Missing Gitiles file payload: ' + name)
                    with stream:
                        payload_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
                records.append({
                    'path': name, 'type': member.type.hex(), 'mode': member.mode,
                    'uid': member.uid, 'gid': member.gid,
                    'uname': member.uname, 'gname': member.gname,
                    'linkname': member.linkname, 'size': member.size,
                    'devmajor': member.devmajor, 'devminor': member.devminor,
                    'paxHeaders': {key: value for key, value in member.pax_headers.items()
                                   if key != 'mtime'},
                    'sha256': payload_hash,
                })
            global_pax = {key: value for key, value in archive.pax_headers.items()
                          if key != 'mtime'}
    except (tarfile.TarError, OSError, EOFError, ValueError) as error:
        if isinstance(error, SourceArchiveMismatch):
            raise
        raise SourceArchiveMismatch('Invalid Gitiles source archive: ' + str(error)) from error
    canonical = {'format': GITILES_CONTENT_FORMAT, 'globalPaxHeaders': global_pax,
                 'members': sorted(records, key=lambda item: item['path'])}
    payload = json.dumps(canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    return {'format': GITILES_CONTENT_FORMAT, 'memberCount': len(records),
            'regularFileCount': file_count, 'regularFileBytes': file_bytes,
            'sha256': hashlib.sha256(payload).hexdigest()}


def verify_archive(entry, path):
    """Preserve original archive SHA; allow only separately pinned Gitiles content."""
    actual = digest(path)
    if actual == entry['archive_sha256']:
        return {'method': 'archive-sha256', 'archiveSha256': actual}
    expected = entry.get('gitiles_content')
    if not expected or not is_pinned_gitiles(entry):
        raise SourceArchiveMismatch('Source archive hash mismatch: ' + entry['id'])
    if (set(expected) != {'format', 'memberCount', 'regularFileCount', 'regularFileBytes', 'sha256'}
            or expected['format'] != GITILES_CONTENT_FORMAT
            or any(type(expected[key]) is not int or expected[key] < 0
                   for key in ('memberCount', 'regularFileCount', 'regularFileBytes'))
            or not re.fullmatch(r'[0-9a-f]{64}', expected['sha256'])):
        raise SourceArchiveMismatch('Invalid Gitiles content pin: ' + entry['id'])
    actual_content = gitiles_content_identity(path, expected)
    if actual_content != expected:
        raise SourceArchiveMismatch('Gitiles source member identity mismatch: ' + entry['id'])
    return {'method': GITILES_CONTENT_FORMAT, 'archiveSha256': actual,
            'contentSha256': actual_content['sha256']}


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
    if path.is_file():
        try:
            verify_archive(entry, path)
            return path
        except SourceArchiveMismatch:
            pass
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
    try:
        verification = verify_archive(entry, temporary)
    except SourceArchiveMismatch as error:
        raise SystemExit(str(error)) from error
    temporary.replace(path)
    if verification['method'] == GITILES_CONTENT_FORMAT:
        print('SOURCE_CONTENT_VERIFIED', entry['id'], verification['contentSha256'],
              '(Gitiles modification timestamps excluded; original archive SHA retained)')
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
    # This marker identifies the reviewed source, including a Gitiles archive
    # whose exact member identity matches despite regenerated tar timestamps.
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
