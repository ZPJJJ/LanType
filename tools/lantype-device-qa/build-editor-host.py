#!/usr/bin/env python3
"""Build the separate, permission-free QA editor without changing the release IME."""
from pathlib import Path
import argparse
import hashlib
import os
import subprocess
import zipfile

SOURCE = Path(__file__).resolve().parent / 'editor-host'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--jdk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'JAVA_HOME': str(args.jdk.resolve()),
           'PATH': str(args.jdk.resolve() / 'bin') + os.pathsep + os.environ.get('PATH', '')}
    build = args.sdk / 'build-tools/36.0.0'
    android = args.sdk / 'platforms/android-36/android.jar'
    generated, classes, dex = (output / name for name in ('generated', 'classes', 'dex'))
    for directory in (generated, classes, dex):
        directory.mkdir(exist_ok=True)

    def run(*command):
        subprocess.run([str(part) for part in command], check=True, env=env)

    run(build / 'aapt2', 'compile', '--dir', SOURCE / 'res', '-o', output / 'resources.zip')
    run(build / 'aapt2', 'link', '-I', android, '--manifest', SOURCE / 'AndroidManifest.xml',
        '--java', generated, '--version-code', '1', '--version-name', '1.0',
        '-o', output / 'unsigned.apk', output / 'resources.zip')
    run(args.jdk / 'bin/javac', '--release', '17', '-encoding', 'UTF-8', '-classpath', android,
        '-d', classes, *sorted((SOURCE / 'src').rglob('*.java')), *sorted(generated.rglob('*.java')))
    run(build / 'd8', '--lib', android, '--min-api', '28', '--output', dex,
        *sorted(classes.rglob('*.class')))
    with zipfile.ZipFile(output / 'unsigned.apk', 'a', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(dex / 'classes.dex', 'classes.dex')
    key = output / 'qa-only.jks'
    if not key.exists():
        # This throwaway fixture key never signs LanType. Keep it outside public source.
        run(args.jdk / 'bin/keytool', '-genkeypair', '-keystore', key, '-storepass', 'android',
            '-keypass', 'android', '-alias', 'qa', '-dname', 'CN=LanType Disposable QA',
            '-keyalg', 'RSA', '-keysize', '2048', '-validity', '3650', '-noprompt')
        key.chmod(0o600)
    run(build / 'zipalign', '-f', '4', output / 'unsigned.apk', output / 'aligned.apk')
    apk = output / 'lantype-editor-host.apk'
    run(build / 'apksigner', 'sign', '--ks', key, '--ks-pass', 'pass:android',
        '--key-pass', 'pass:android', '--out', apk, output / 'aligned.apk')
    run(build / 'apksigner', 'verify', apk)
    with apk.open('rb') as stream:
        print(apk, apk.stat().st_size, hashlib.file_digest(stream, 'sha256').hexdigest())


if __name__ == '__main__':
    main()
