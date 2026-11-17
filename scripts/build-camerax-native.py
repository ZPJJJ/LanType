#!/usr/bin/env python3
"""Build only the two CameraX JNI libraries from their supplied pinned sources."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'vendor/lantype-camerax-native/arm64-v8a'
LOCK = ROOT / 'docs/licensing/camerax-rebuilt.lock.json'
NDK_VERSION = '27.2.12479018'
CMAKE_VERSION = '3.22.1'
LIBRARIES = ('libimage_processing_util_jni.so', 'libsurface_util_jni.so')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verified():
    if not LOCK.is_file():
        return False
    lock = json.loads(LOCK.read_text())
    wanted_paths = {str((OUTPUT / name).relative_to(ROOT)) for name in LIBRARIES}
    if {entry['path'] for entry in lock.get('outputs', [])} != wanted_paths or len(lock['outputs']) != 2:
        return False
    if lock.get('buildScriptSha256') != digest(ROOT / 'scripts/camerax-native/CMakeLists.txt'):
        return False
    source_lock = json.loads((ROOT / 'docs/licensing/native-sources.lock.json').read_text())
    current_inputs = {entry['id']: (entry.get('commit'), entry['archive_sha256']) for entry in source_lock['sources']}
    if any(current_inputs.get(entry['id']) != (entry['commit'], entry['archive_sha256']) for entry in lock['sourceInputs']):
        return False
    return all((ROOT / entry['path']).is_file() and digest(ROOT / entry['path']) == entry['sha256']
               and (ROOT / entry['path']).stat().st_size == entry['size'] for entry in lock['outputs'])


def verify_apk(apk):
    lock = json.loads(LOCK.read_text())
    expected_paths = {'lib/arm64-v8a/' + name for name in LIBRARIES}
    if len(lock['outputs']) != 2 or {'lib/arm64-v8a/' + Path(entry['path']).name for entry in lock['outputs']} != expected_paths:
        raise SystemExit('CameraX lock must contain exactly the two reviewed ARM64 outputs.')
    records = []
    with zipfile.ZipFile(apk) as archive:
        for entry in lock['outputs']:
            basename = Path(entry['path']).name
            expected = 'lib/arm64-v8a/' + basename
            occurrences = [item for item in archive.infolist() if item.filename.startswith('lib/') and Path(item.filename).name == basename]
            if len(occurrences) != 1 or occurrences[0].filename != expected:
                raise SystemExit('APK must contain exactly one ARM64 copy and no other ABI copy of ' + basename)
            with archive.open(occurrences[0]) as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if occurrences[0].file_size != entry['size'] or actual != entry['sha256']:
                raise SystemExit('APK retained an incorrect CameraX JNI payload: ' + expected)
            records.append({'path': expected, 'size': entry['size'], 'sha256': actual, 'uniqueAcrossAbis': True})
    print(json.dumps({'pass': True, 'apk': str(apk), 'sourceBuiltCameraX': records}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-dir', type=Path, default=ROOT / '.gradle/native-source-archives')
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--verify-apk', type=Path, help='Prove the final APK contains exactly the two locked source-built JNI outputs')
    parser.add_argument('--rebuild', action='store_true')
    parser.add_argument('--record-lock', action='store_true', help='Maintainer operation: record a newly reviewed build')
    args = parser.parse_args()
    if args.verify_apk:
        verify_apk(args.verify_apk)
        return
    if verified() and not args.rebuild:
        print('CAMERAX_NATIVE_VERIFIED: two source-built, locked ARM64 JNI libraries')
        return
    if args.verify_only:
        raise SystemExit('CameraX JNI output missing/changed; run scripts/build-camerax-native.py --download or restore the runtime attachment.')
    sdk = Path(os.environ.get('ANDROID_HOME', os.environ.get('ANDROID_SDK_ROOT', '')))
    ndk = sdk / 'ndk' / NDK_VERSION
    cmake = sdk / 'cmake' / CMAKE_VERSION / 'bin/cmake'
    ninja = cmake.with_name('ninja')
    if not cmake.is_file() or not (ndk / 'build/cmake/android.toolchain.cmake').is_file():
        raise SystemExit(f'Install Android SDK packages ndk;{NDK_VERSION} and cmake;{CMAKE_VERSION} first.')
    spec = importlib.util.spec_from_file_location('native_sources', ROOT / 'scripts/restore-native-sources.py')
    restore = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(restore)
    source_lock = json.loads((ROOT / 'docs/licensing/native-sources.lock.json').read_text())
    wanted = ('androidx-camera-core', 'lantype-camerax-libyuv')
    entries = {entry['id']: entry for entry in source_lock['sources'] if entry['id'] in wanted}
    for entry in entries.values():
        restore.extract(entry, restore.obtain(entry, args.archive_dir, args.download))
    camera = ROOT / entries['androidx-camera-core']['installPath']
    yuv = ROOT / entries['lantype-camerax-libyuv']['installPath']
    build = ROOT / '.gradle/lantype-camerax-native'
    command = [str(cmake), '-S', str(ROOT / 'scripts/camerax-native'), '-B', str(build), '-G', 'Ninja',
               '-DCMAKE_MAKE_PROGRAM=' + str(ninja), '-DCMAKE_TOOLCHAIN_FILE=' + str(ndk / 'build/cmake/android.toolchain.cmake'),
               '-DANDROID_ABI=arm64-v8a', '-DANDROID_PLATFORM=android-28', '-DANDROID_STL=c++_static',
               '-DANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON', '-DCMAKE_BUILD_TYPE=Release',
               '-DCAMERAX_SOURCE=' + str(camera), '-DLIBYUV_SOURCE=' + str(yuv), '-DLANTYPE_ROOT=' + str(ROOT)]
    subprocess.run(command, check=True)
    subprocess.run([str(cmake), '--build', str(build), '--parallel', '2', '--target', 'image_processing_util_jni', 'surface_util_jni'], check=True)
    strip = ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip'
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in LIBRARIES:
        origin = build / 'camera-core-jni' / name
        target = OUTPUT / name
        shutil.copyfile(origin, target)
        subprocess.run([str(strip), '--strip-unneeded', str(target)], check=True)
    receipt = {'schemaVersion': 1, 'edition': 'LanType 1.1.0', 'cameraVersion': '1.6.2',
               'sourceInputs': [{key: entry[key] for key in ('id', 'commit', 'archive_sha256')} for entry in entries.values()],
               'ndk': NDK_VERSION, 'cmake': CMAKE_VERSION, 'abi': 'arm64-v8a', 'minSdk': 28,
               'stl': 'c++_static', 'pageSize': 16384, 'jpegEnabled': False,
               'buildScript': 'scripts/camerax-native/CMakeLists.txt',
               'buildScriptSha256': digest(ROOT / 'scripts/camerax-native/CMakeLists.txt'),
               'outputs': [{'path': str((OUTPUT / name).relative_to(ROOT)), 'size': (OUTPUT / name).stat().st_size,
                            'sha256': digest(OUTPUT / name)} for name in LIBRARIES]}
    if args.record_lock:
        LOCK.write_text(json.dumps(receipt, indent=2) + '\n')
    elif not verified():
        raise SystemExit('Rebuilt output differs from the reviewed native lock; do not silently update it. Investigate toolchain/input differences.')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
