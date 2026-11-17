# LanType 1.1.0

LanType is an independent GPLv3 Android keyboard derived from CyIME 1.15.94 and Rime. It supports Chinese and American English on Android 9+ ARM64 devices. The application has no `INTERNET` permission; development dependencies may be downloaded on the build computer.

The new Tool Cabin provides local unit conversion, explicit selection-based text transformations, and dynamic templates with date/time and a cursor slot. Text is previewed before insertion. Clipboard templates require explicit confirmation. Password and restricted fields are blocked, and stale selections cannot be silently replaced.

The commercial resource set uses AOSP/rime-pinyin-simp and CC-CEDICT Chinese dictionaries, SCOWL American English, Whisper multilingual base INT8 speech recognition, PP-OCRv5 OCR, and MakeMeAHanzi-derived stroke-order handwriting templates. Chinese handwriting is single-character template matching; it is not a claim of cursive or whole-line recognition. Model changes require new device testing.

GPLv3 permits charging for distribution while recipients retain their GPL rights, including corresponding source and redistribution. Data, model and graphical resources retain their individual licenses. No online activation is required. Source archives must accompany the actual released binaries, including the corresponding native components and build instructions.

See the [main README](README.md), [installation guide](docs/INSTALLATION.zh-CN.md), [privacy notice](docs/PRIVACY.zh-CN.md), [commercial plan](docs/COMMERCIAL-PLAN.zh-CN.md), and [build/source documentation](docs/LANTYPE-BUILD-AND-SOURCES.md). Full third-party notices are bundled in the application and readable offline.

This is not an official CyIME release. Original copyright, source attribution and license notices are preserved. The [1.1.0 validation report](docs/validation-1.1.0/VALIDATION.md) distinguishes host-side tests from testing on real ARM64 devices and store approval.
