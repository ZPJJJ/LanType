#!/usr/bin/env python3
"""Package the actual locked native source archives, not a URL-only source offer."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    lock_path = ROOT / 'docs/licensing/native-sources.lock.json'
    lock = json.loads(lock_path.read_text())
    files = []
    for entry in lock['sources']:
        path = args.archive_dir / entry['archive_file']
        if not path.is_file() or path.stat().st_size != entry['archive_bytes'] or sha256(path) != entry['archive_sha256']:
            raise SystemExit(f"Missing or changed actual source: {entry['id']}")
        files.append((path, 'archives/' + path.name, entry['archive_sha256']))
    readme = """# LanType 1.1.0 corresponding native source attachment

This is an actual source distribution: archives/ contains the complete fixed
source archives whose SHA-256 values appear in native-sources.lock.json.
Keep it with the separately distributed LanType application source ZIP, which
contains the current Java/Kotlin code, JNI wrappers, build scripts and patches.

It includes Rime and its recursive dependencies, Boost, the original CyIME
native wrapper/build sources, Sherpa 1.13.8 plus static speech dependencies,
ONNX Runtime 1.28.0 and Sherpa's static 1.28.2 plus Android dependency sources,
OpenCV 4.12.0, Sora editor 0.24.6, CameraX/Graphics native modules and their
official Maven source JARs. Each archive preserves upstream notices.
The original CyIME archive is filtered to native/build code; no upstream model,
corpus, keyboard asset or personal test fixture is included.

From the application source root, verify every archive:

    python3 scripts/restore-native-sources.py --archive-dir /path/to/this/archives --all --verify-only

Restore the JNI prerequisites locally:

    python3 scripts/restore-native-sources.py --archive-dir /path/to/this/archives
    python3 scripts/prepare-native-build.py
    ./gradlew :app:assembleOffline -Plantype.nativeFromSource=true

See docs/LANTYPE-BUILD-AND-SOURCES.md for tools, options, dependency preparation,
and tested scope. --all additionally restores the separate runtime/dependency
trees for rebuilding those upstream projects with their supplied build scripts.
The standard LanType build reuses hash-locked native binaries. Binary-identical
native reproduction is not claimed. The CameraX JNI pair is actually rebuilt from the exact 1.6.2 module sources
with explicitly pinned AOSP libyuv; camerax-rebuilt.lock.json and
scripts/camerax-native in the application source record the build. The original
opaque Maven native pair is replaced, not represented as source-identical to
our selected libyuv version. See correspondenceStatus in the lock. Android SDK/NDK and signing keys are not
included; a derivative may use its own key. No device attestation or activation
secret is needed to build/install a self-signed derivative.
"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for source, target, _ in files:
            info = zipfile.ZipInfo(target, (2026, 11, 17, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            with source.open('rb') as stream, archive.open(info, 'w', force_zip64=True) as dest:
                while chunk := stream.read(1024 * 1024):
                    dest.write(chunk)
        archive.writestr('native-sources.lock.json', lock_path.read_bytes())
        archive.writestr('README.md', readme)
        archive.writestr('GPL-LICENSE.txt', (ROOT / 'LICENSE').read_bytes())
        archive.writestr('SOURCE-SHA256SUMS.txt', ''.join(f'{digest}  {name}\n' for _, name, digest in files))
    receipt = {'file': args.output.name, 'sha256': sha256(args.output), 'size': args.output.stat().st_size,
               'actualSourceArchives': len(files), 'sourceArchiveBytes': sum(path.stat().st_size for path, _, _ in files),
               'containsProductRuntimeModelsOrCorpora': False, 'containsSigningSecrets': False,
               'binaryIdenticalNativeReproductionEstablished': False,
               'remainingPinEvidenceGap': lock.get('correspondenceStatus', {}).get('remainingPinEvidenceGap', [])}
    args.output.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
