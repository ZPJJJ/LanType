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
