# LanType device QA editor

This small native Android app provides disposable ordinary, password, email and number fields for testing the **separately installed, unchanged LanType APK**. It does not replace the IME service or mock its engine. It has no requested permissions, no network access, no input logging and no app-owned persistent storage. Use fictional text only on an explicitly selected disposable emulator or authorized test device.

Build with the existing Android SDK and JDK; the output must be outside the tracked source tree:

```sh
python3 tools/lantype-device-qa/build-editor-host.py \
  --sdk /path/to/android-sdk --jdk /path/to/jdk \
  --output /path/to/disposable-qa-output
```

Install `lantype-editor-host.apk` only on the selected test device. Its package is `app.lantype.testhost`. The generated throwaway fixture key is unrelated to the product signing key and is not a release asset.

Use UI hierarchy bounds for taps. Type through the real LanType keyboard, then inspect the native editor text and the length/selection status. `Text A` and `Text B` have separate input connections; field switching can verify stale-selection protections. `Mask sample` seeds explicitly fictional input for selection transforms. `Clipboard` explicitly sets a synthetic clipboard value, allowing template expansion to be checked without reading any real clipboard. Password tests should use fictional text and avoid capturing entered password values.

Test evidence must identify device serial, Android version, ABI, native bridge if any, installed APK hash and each observed result. An x86 emulator with ARM translation does not establish physical ARM64 latency, battery usage or 16 KiB device compatibility.

## Fixed public release downloads

`fetch-release-apks.py` downloads the signed `v1.1.1-rc1` APK first, then the signed `v1.1.0-rc1` APK, from fixed public GitHub release URLs. The new candidate must be published before this preflight can succeed. It uses no API token or other download credentials and accepts only HTTPS redirects to the approved GitHub download hosts. Both APKs must match their fixed byte counts and SHA-256 hashes before the workflow starts a VM.

```sh
python3 tools/lantype-device-qa/fetch-release-apks.py \
  --output /path/to/disposable-qa-output/apks \
  --receipt /path/to/disposable-qa-output/evidence/release-apks.json
```

An unavailable release, HTTP 403/404, interrupted download or hash mismatch is a blocked download prerequisite, not an observed product failure. The previous draft-asset attempt returned HTTP 403 with `contents: read`; no VM or product was started. This public-download workflow keeps the same read-only repository permission and does not request a more privileged token.

## Signed APK upgrade smoke

On a **fresh disposable emulator**, with the SDK tools available, run:

```sh
ANDROID_SERIAL=emulator-5554 python3 tools/lantype-device-qa/run-device-smoke.py \
  --old-apk /path/to/LanType-1.1.0-offline-arm64-v8a.apk \
  --new-apk /path/to/LanType-1.1.1-offline-arm64-v8a.apk \
  --host-apk /path/to/lantype-editor-host.apk \
  --output /path/to/new-smoke-evidence
```

The driver requires an `emulator-*` serial, `ro.kernel.qemu=1`, current Android user 0 and `RUNNING_UNLOCKED` before changing radio settings or installing anything. It disables guest networking before the first product launch, performs streaming installs without downgrade/clear/uninstall, waits for actual first-run Rime preparation, and uses `adb ime enable/set` for the system provisioning steps. It then taps real accessible keyboard keys for `nihao` → `你好` and US English `color`, explicitly saves the C# template, replaces the APK, and checks input plus the saved template through the visible UI. The upgraded template check first selects Lua, then loads “My template”, so it cannot pass merely by observing the default C# preset.

Every touch uses bounds from a fresh UI XML, accompanied by a screenshot. The script does not treat Compose test tags as Android resource IDs or use `adb input text` as proof of keyboard input. Missing or ambiguous nodes fail with evidence. `result.json` records each observed pass, failure, blocked prerequisite and unrun extension separately; `commands.jsonl` and failure diagnostics retain the execution details. Optional unit conversion is reported separately from required core cases. Private clipboard/process-restart checks are explicitly **not run** in this first core workflow. This verifies ordinary release-to-release data retention, not seeded legacy-directory conflicts, physical-device acceptance or a 16 KiB runtime test.
