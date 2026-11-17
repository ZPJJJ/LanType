#!/usr/bin/env python3
"""Verify approved source/APK assets and reject removed payloads in public archives."""
from pathlib import Path, PurePosixPath
import argparse
import gzip
import hashlib
import io
import json
import re
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(stream):
    digest, count, prefix = hashlib.sha256(), 0, b''
    while chunk := stream.read(1024 * 1024):
        if not prefix:
            prefix = chunk[:8]
        digest.update(chunk)
        count += len(chunk)
    return count, digest.hexdigest(), prefix


def file_fingerprint(path):
    with path.open('rb') as stream:
        return fingerprint(stream)


def zip_fingerprint(archive, name, expand=False):
    item = getattr(archive, '_lantype_utf8_entries', {}).get(name, name)
    with archive.open(item) as stream:
        if expand:
            with gzip.GzipFile(fileobj=stream, mode='rb') as decoded:
                return fingerprint(decoded)
        return fingerprint(stream)


def raw_path(entry):
    relative = entry['path']
    if relative.startswith('app/src/main/res/'):
        return ROOT / relative
    if relative.startswith('res/'):
        return ROOT / 'app/src/main' / relative
    return ROOT / 'app/src/main/res' / (relative if relative.startswith('raw/') else 'raw/' + relative)


def validate_path(relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe resource path')


def locks():
    lock = json.loads((ROOT / 'docs/licensing/resources.lock.json').read_text())
    removed = json.loads((ROOT / 'docs/licensing/excluded-resources.json').read_text())['excluded']
    denied = {entry['sha256']: entry for entry in removed}
    approved = {entry['sha256'] for entry in lock['resources'] + lock.get('rawResources', [])}
    return lock, denied, approved


def deny_result(name, digest, denied, approved, encoding='identity'):
    # Full licence text and deliberately retained reviewed bytes take precedence.
    if digest in approved or digest not in denied:
        return None
    return {'path': name, 'reason': 'removed payload content hash found', 'encoding': encoding,
            'matchesOldPath': denied[digest]['oldPath'], 'sha256': digest}


def scan_zip(archive, denied, approved):
    failures, inventory = [], {}
    archive._lantype_utf8_entries = {}
    archive._lantype_filename_corrections = []
    for item in archive.infolist():
        name = item.filename
        # AAPT can write UTF-8 name bytes without ZIP's language-encoding flag.
        # Android AssetManager uses those UTF-8 bytes; Python otherwise shows
        # a CP437 mojibake name. Recover the actual bytes, never fuzzy-match paths.
        if not item.flag_bits & 0x800:
            try:
                decoded = name.encode('cp437').decode('utf-8')
                if decoded != name:
                    archive._lantype_filename_corrections.append({'zipDisplayName': name, 'androidUtf8Name': decoded})
                    name = decoded
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        if name.endswith('/'):
            continue
        if name in inventory:
            failures.append({'path': name, 'reason': 'duplicate ZIP member'})
        archive._lantype_utf8_entries[name] = item
        size, digest, prefix = zip_fingerprint(archive, name)
        inventory[name] = (size, digest, prefix)
        finding = deny_result(name, digest, denied, approved)
        if finding:
            failures.append(finding)
        if prefix.startswith(b'\x1f\x8b'):
            try:
                _, inner, _ = zip_fingerprint(archive, name, expand=True)
                finding = deny_result(name, inner, denied, approved, 'gzip-expanded')
                if finding:
                    failures.append(finding)
            except (OSError, EOFError):
                failures.append({'path': name, 'reason': 'malformed gzip payload'})
    return failures, inventory


def generated_asset(archive, name, actual):
    """Allow generated content only when its exact source/format is established."""
    relative = name.removeprefix('assets/')
    expected = None
    if relative.startswith('plugin-market/'):
        suffix = relative.removeprefix('plugin-market/')
        if suffix.startswith('packages/') or suffix.endswith('.xipk'):
            return None
        expected = ROOT / 'store/plugins' / suffix
    elif relative.startswith('release-notes/') and re.fullmatch(r'release-notes/\d+\.\d+\.\d+\.md', relative):
        expected = ROOT / 'docs/releases/lantype' / Path(relative).name
    elif relative == 'builtin-plugins/windows-clipboard.xipk':
        if actual[0] > 2 * 1024 * 1024:
            return None
        with zipfile.ZipFile(io.BytesIO(archive.read(name))) as package:
            if set(package.namelist()) != {'manifest.yaml', 'main.lua'}:
                return None
            entries = []
            for child in sorted(package.namelist()):
                source = ROOT / 'plugins/cyime-windows-sync' / child
                matched = zip_fingerprint(package, child)[:2] == file_fingerprint(source)[:2]
                if not matched:
                    return None
                entries.append({'path': child, 'sha256': file_fingerprint(source)[1]})
            return {'path': relative, 'basis': 'exact two-file package built from the published GPL plugin source', 'entries': entries}
    elif relative in ('dexopt/baseline.prof', 'dexopt/baseline.profm'):
        magic = b'prm\x00' if relative.endswith('.profm') else b'pro\x00'
        if actual[0] <= 8 * 1024 * 1024 and actual[2].startswith(magic):
            return {'path': relative, 'basis': 'AGP-generated ART profile, exact path, bounded size and binary magic', 'sha256': actual[1]}
        return None
    if expected is not None and expected.is_file() and not expected.is_symlink() and file_fingerprint(expected)[:2] == actual[:2]:
        return {'path': relative, 'basis': 'exact published source bytes', 'sourcePath': str(expected.relative_to(ROOT)), 'sha256': actual[1]}
    return None


def check(apk=None):
    lock, denied, approved = locks()
    failures, checked, generated, native_replacements = [], [], [], []
    expected = lock['resources']
    generated_names = {entry['path'] for entry in lock.get('generatedAssets', [])}
    full_zip_count, filename_corrections = 0, []
    if apk:
        archive = zipfile.ZipFile(apk)
        denied_findings, inventory = scan_zip(archive, denied, approved)
        failures.extend(denied_findings)
        full_zip_count = len(inventory)
        filename_corrections = archive._lantype_filename_corrections
    else:
        archive, inventory = None, {}
    consumed = set()
    try:
        for entry in expected:
            relative = entry['path']
            validate_path(relative)
            actual, packaged, encoding = None, None, 'identity'
            target = (entry['size'], entry['sha256'])
            if archive:
                packaged = 'assets/' + relative
                if packaged in inventory:
                    actual = inventory[packaged][:2]
                elif packaged + '.gz' in inventory:
                    packaged += '.gz'
                    actual = zip_fingerprint(archive, packaged, expand=True)[:2]
                    encoding = 'extra-gzip'
                elif relative.endswith('.gz') and 'assets/' + relative[:-3] in inventory:
                    packaged = 'assets/' + relative[:-3]
                    original = ROOT / 'app/src/main/assets' / relative
                    if original.is_file() and file_fingerprint(original)[:2] == target:
                        with gzip.open(original, 'rb') as decoded:
                            expanded = fingerprint(decoded)[:2]
                        if expanded == inventory[packaged][:2]:
                            actual, encoding = target, 'aapt-expanded-source-gzip'
                if actual is not None:
                    consumed.add(packaged)
            else:
                source = ROOT / 'app/src/main/assets' / relative
                if source.is_file() and not source.is_symlink():
                    actual = file_fingerprint(source)[:2]
            if actual is None:
                failures.append({'path': relative, 'reason': 'missing or unexpected packaging transformation'})
            elif actual != target:
                failures.append({'path': relative, 'reason': 'size or SHA-256 differs from approved lock'})
            else:
                checked.append({'path': relative, 'packagedPath': packaged, 'encoding': encoding, 'sha256': entry['sha256'], 'size': entry['size']})
        if archive:
            camera_lock = json.loads((ROOT / 'docs/licensing/camerax-rebuilt.lock.json').read_text())
            if len(camera_lock['outputs']) != 2:
                failures.append({'path': 'camerax-rebuilt.lock.json', 'reason': 'expected exactly two replacement outputs'})
            for entry in camera_lock['outputs']:
                name = 'lib/arm64-v8a/' + Path(entry['path']).name
                actual = inventory.get(name)
                valid = actual is not None and actual[:2] == (entry['size'], entry['sha256'])
                native_replacements.append({'path': name, 'matchesSourceBuiltLock': valid, 'sha256': actual[1] if actual else None})
                if not valid:
                    failures.append({'path': name, 'reason': 'APK does not contain the locked source-built CameraX replacement'})
                old = entry.get('originalMavenSha256')
                if old and any(value[1] == old for value in inventory.values()):
                    failures.append({'path': name, 'reason': 'original opaque Maven JNI payload remains in the APK'})
            for name, actual in inventory.items():
                if name.startswith('assets/') and name not in consumed:
                    allowed = generated_asset(archive, name, actual) if name.removeprefix('assets/') in generated_names else None
                    if allowed:
                        generated.append(allowed)
                    else:
                        failures.append({'path': name, 'reason': 'asset outside reviewed whitelist / exact generated inputs'})
                if name.endswith('.xipk') and name != 'assets/builtin-plugins/windows-clipboard.xipk':
                    failures.append({'path': name, 'reason': 'unapproved prebuilt plugin package'})
            raw_hashes = {actual[1] for name, actual in inventory.items() if name.startswith('res/')}
            for entry in lock.get('rawResources', []):
                if entry['sha256'] not in raw_hashes:
                    failures.append({'path': entry['path'], 'reason': 'approved raw resource missing by exact content hash'})
        else:
            expected_names = {entry['path'] for entry in expected}
            for source in (ROOT / 'app/src/main/assets').rglob('*'):
                if source.is_file() and source.name != '.gitignore' and str(source.relative_to(ROOT / 'app/src/main/assets')) not in expected_names:
                    failures.append({'path': str(source.relative_to(ROOT)), 'reason': 'asset outside reviewed whitelist'})
            for entry in lock.get('rawResources', []):
                source = raw_path(entry)
                if not source.is_file() or file_fingerprint(source)[:2] != (entry['size'], entry['sha256']):
                    failures.append({'path': entry['path'], 'reason': 'raw source size/hash mismatch'})
    finally:
        if archive:
            archive.close()
    return {'schemaVersion': 1, 'edition': '1.1.0', 'mode': 'apk' if apk else 'source',
            'apk': str(apk) if apk else None, 'lockSha256': file_fingerprint(ROOT / 'docs/licensing/resources.lock.json')[1],
            'approvedAssetCount': len(expected), 'checkedAssetCount': len(checked), 'rawResourceCount': len(lock.get('rawResources', [])),
            'allZipEntriesScanned': full_zip_count, 'zipFilenameEncodingCorrections': filename_corrections,
            'generatedAssets': generated, 'cameraNativeReplacements': native_replacements,
            'pass': not failures, 'failures': failures, 'assets': checked}


def check_public_payloads(source_zip=None):
    _, denied, approved = locks()
    if source_zip:
        with zipfile.ZipFile(source_zip) as archive:
            failures, inventory = scan_zip(archive, denied, approved)
        count = len(inventory)
    else:
        result = subprocess.run(['git', 'ls-files', '--stage', '-z'], cwd=ROOT, capture_output=True, check=True)
        entries = [value for value in result.stdout.decode().split('\0') if value]
        failures, count = [], len(entries)
        process = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            for record in entries:
                metadata, relative = record.split('\t', 1)
                mode, oid, stage = metadata.split()
                if stage != '0' or mode == '120000':
                    failures.append({'path': relative, 'reason': 'unmerged or symlink index entry'})
                    continue
                process.stdin.write((oid + '\n').encode())
                process.stdin.flush()
                header = process.stdout.readline().decode().strip().split()
                if len(header) != 3 or header[1] != 'blob':
                    raise ValueError('Git index object is not a readable blob')
                remaining, digest, prefix = int(header[2]), hashlib.sha256(), b''
                with tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024) as compressed:
                    while remaining:
                        chunk = process.stdout.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise EOFError('Truncated Git blob stream')
                        if not prefix:
                            prefix = chunk[:8]
                        digest.update(chunk)
                        if prefix.startswith(b'\x1f\x8b'):
                            compressed.write(chunk)
                        remaining -= len(chunk)
                    if process.stdout.read(1) != b'\n':
                        raise ValueError('Unexpected Git batch delimiter')
                    finding = deny_result(relative, digest.hexdigest(), denied, approved)
                    if finding:
                        failures.append(finding)
                    if prefix.startswith(b'\x1f\x8b'):
                        compressed.seek(0)
                        with gzip.GzipFile(fileobj=compressed, mode='rb') as decoded:
                            _, expanded, _ = fingerprint(decoded)
                        finding = deny_result(relative, expanded, denied, approved, 'gzip-expanded-index-blob')
                        if finding:
                            failures.append(finding)
        finally:
            process.stdin.close()
            process.wait()
    return {'schemaVersion': 1, 'edition': '1.1.0', 'mode': 'source-zip' if source_zip else 'git-index',
            'scannedFiles': count, 'byteSource': 'ZIP entries' if source_zip else 'actual staged Git blobs via cat-file', 'approvedHashesTakePrecedence': True, 'removedContentHashes': len(denied), 'pass': not failures, 'failures': failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apk', type=Path)
    mode.add_argument('--source-zip', type=Path)
    mode.add_argument('--git-index', action='store_true')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    report = check_public_payloads(args.source_zip) if args.source_zip or args.git_index else check(args.apk)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key not in ('assets', 'generatedAssets')}, ensure_ascii=False, indent=2))
    if not report['pass']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
