# Whisper language-switch regression

Review baseline: `60903e8`. This note covers the dictation backend only; it does not certify recognition accuracy or device performance.

## Defect and change

The packaged Whisper recognizer is created with `OfflineWhisperModelConfig.language` fixed to `zh` or `en` in `speech/SherpaSpeechEngine.kt`. Before this change, `OfflineAsrBackend.canContinueIn` checked only model compatibility and the selected model ID. Both Chinese and English select the same Whisper model, so switching languages during a recording incorrectly retained the old decoder language.

`OfflineAsrBackend` now records the language of a successfully started session. Whisper can continue only in that language. A failed bind/start and explicit model unload clear the reusable configuration. Other recognizer modes retain their existing compatibility check.

The existing `SpeechRecognitionManager.deliverAudio` transition is unchanged. It finishes the old segment, retains completed text, invalidates the old callbacks, starts the new language, and delivers queued audio using the same microphone capture session.

## Resident-cache review

The following production call chain was inspected:

1. `OfflineAsrBackend.start(language)` passes an explicit language to `AsrInferenceClient.startAsr`.
2. The client calls `startAsrForLanguage(modelId, language.id, callback)` over its existing service interface.
3. `AsrInferenceService.startDictation` calls `AsrModelManager.selection(modelId, language)`.
4. `AsrModelManager.Selection.key` includes both the model ID and `recognitionLanguage`, followed by model-directory/file metadata.
5. `ResidentSpeechSessionOwner.start` closes and recreates its engine when that key changes; it reuses the engine for an unchanged key.

Therefore no service cache-key or JNI configuration change was required. Restarting Chinese as English reaches a distinct resident key even when the weight files are identical.

## Focused regression coverage

`OfflineWhisperLanguageSwitchTest` contains five tests:

- Chinese → English → Chinese with the same selected Whisper model requests distinct language sessions.
- A failed remote start cannot leave the previous configuration reusable.
- A failed bind cannot leave the previous configuration reusable.
- An explicitly unloaded backend cannot continue in its previous language.
- Real `Selection.key` values and the real `ResidentSpeechSessionOwner` replace the engine for another language and reuse it for a repeated language.

The backend tests replace IPC and model selection with mocks. The cache test uses temporary fixture files and mocked native engines; it executes the production key construction and ownership logic. No microphone or native recognizer runs in these five tests.

Requested existing manager regressions cover microphone continuity, completed-text preservation, stale callback rejection, and the unchanged generic bilingual-backend reuse path:

- `SpeechRecognitionLanguageSessionTest.japaneseEnglishJapaneseSwitchKeepsOneMicrophoneAndPreservesCompletedText`
- `SpeechRecognitionLanguageSessionTest.compatibleBilingualModelDoesNotRestartWhenKeyboardLanguageChanges`

## Execution status

The 2026-11-17 serial Android Gradle batch executed all five `OfflineWhisperLanguageSwitchTest` cases and all 22 existing `SpeechRecognitionLanguageSessionTest` cases. Both classes passed with zero failures, errors or skips. Raw XML is preserved under `../validation-1.1.1/junit/final/`.

The complete first serial batch executed 96 cases; its two failures were clipboard-test timestamp preconditions, outside these speech classes. That distinction is preserved in `../validation-1.1.1/junit/first-serial/`. An earlier overlapping emulator/build attempt lost its Gradle daemon before producing a new test result and is not counted as a pass. `git diff --check` also passed.

There is no ARM-device or microphone-recognition acceptance result in this note.
