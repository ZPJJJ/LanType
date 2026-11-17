# Reviewed offline resources

This directory prepares the resources used by LanType 1.1.0. Application
source and native corresponding source are supplied alongside the release.
The app does not download these resources at runtime.

## Prepare a fresh source checkout

From the repository root, using Python 3.10 or later:

```sh
python3 tools/lantype_resources/prepare_resources.py --download
python3 scripts/verify-commercial-resources.py
```

The first command verifies and expands the committed, hash-locked editable
dictionary/graphics inputs. It regenerates the English trie, Chinese tables,
glide/key indexes, original examples, original key tones, stroke templates,
Public Suffix List encoding and Rime deployment manifest. It downloads only
the explicitly pinned Whisper, PP-OCR and Silero model files that are missing,
and checks their sizes and SHA-256 values. It does not read the predecessor
APK or vendor assets. Network access here is for development only.

Without `--download`, already present model files are verified. A directory
containing the three pinned Whisper files can be supplied with
`--model-cache /path/to/whisper-files`. `--skip-models` regenerates only small
data and cannot produce a complete installable offline package by itself.

Native libraries have a separate approved source/prebuilt workflow owned by
`scripts/prepare-upstream.py` and the native source locks.

## Review and verification

`docs/licensing/resources.lock.json` is the reviewed distribution whitelist.
Each main asset has its physical path, logical APK path, size, SHA-256,
origin, fixed revision, license, transformation and authorship status.
`sourceDatasets` describes editable inputs; `rawResources` covers original
WAV files. The full licenses and attribution notices are under
`app/src/main/assets/licenses/` and are readable offline in the application.

To check the actual artifacts:

```sh
python3 scripts/verify-commercial-resources.py --apk /path/to/final.apk --json /path/to/apk-resource-check.json
python3 scripts/verify-commercial-resources.py --source-zip /path/to/source.zip --json /path/to/source-resource-check.json
python3 scripts/verify-commercial-resources.py --git-index --json /path/to/public-source-check.json
```

The APK check streams ZIP entries, checks the approved asset bytes, validates
the small generated assets against their source, and rejects known removed
payload hashes. Source archive checks include gzip expansion. They are an
enforceable check of the reviewed inputs and known excluded bytes, not a
general legal opinion about every possible third-party work.

Only after a deliberate resource/licensing review should a maintainer run:

```sh
python3 tools/lantype_resources/finalize_resources.py --write-lock
```

CI must verify the committed lock. It must not regenerate the lock merely
to make unexpected resource changes pass.

## Resource boundaries

Chinese pinyin tables use the Apache-2.0 Android-derived Rime dictionary and
CC-BY-SA-4.0 CC-CEDICT snapshot. English words use the SCOWL US list with
original editorial ranks. Original small examples replace corpus statistics;
local user learning remains available. These changes do not promise the
ranking quality of the old mixed-corpus data.

Speech uses the MIT-licensed multilingual Whisper base INT8 conversion. The
app offers Chinese and English whole-segment transcription, without live
streaming preview or speaker identification. PP-OCRv5 and Silero VAD retain
their separate Apache-2.0 and MIT notices.

Chinese handwriting uses MakeMeAHanzi/Arphic stroke medians; only the Latin
letters/digits are original LanType geometric templates. It recognizes one
character per pause and expects conventional stroke order. It is not a
neural cursive, whole-word or formula recognizer. The Arphic source and
license are retained separately from the CC0 Latin templates.

KaTeX JavaScript/CSS are MIT; its unchanged fonts are OFL-1.1 according to
the exact release fonts' own metadata. The two licenses must not be confused.

## Evidence scope

`StrokeProbe.kt` and `VocabularyProbe.kt` exercise the production matcher
and English query code on a host JVM. `probe_stubs/GlideCandidate.kt` is only
a DTO used by that host compilation. The reports under
`docs/validation-1.1.0/` identify the exact source hashes and their limitations.
Robolectric asset tests verify actual AAPT/AssetManager file access. Neither
host timing nor Robolectric replaces ARM64 microphone, keyboard or candidate
quality acceptance on a real Android device.
