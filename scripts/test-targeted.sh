#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export CYIME_RENDER_OUT="${CYIME_RENDER_OUT:-$PWD/app/build/lantype-test-renders}"
mkdir -p "$CYIME_RENDER_OUT"
if (( $# == 0 )); then
  set -- \
    com.kingzcheung.xime.toolcabin.UnitConverterTest \
    com.kingzcheung.xime.toolcabin.TextTransformsTest \
    com.kingzcheung.xime.toolcabin.DynamicTemplateTest \
    com.kingzcheung.xime.service.ToolCabinEditorTest \
    com.kingzcheung.xime.service.ToolCabinQueueBoundaryTest \
    com.kingzcheung.xime.service.InputPrivacyTest \
    com.kingzcheung.xime.clipboard.PrivateClipMemoryTest \
    com.kingzcheung.xime.clipboard.ToolCabinClipPrivacyTest \
    com.kingzcheung.xime.clipboard.ClipboardSensitiveTest \
    com.kingzcheung.xime.ui.keyboard.ToolPanelPrivateClipboardTest \
    com.kingzcheung.xime.speech.OfflineWhisperLanguageSwitchTest \
    com.kingzcheung.xime.speech.SpeechRecognitionLanguageSessionTest \
    com.kingzcheung.xime.rime.LegacyRimeDirectoryMigrationTest \
    com.kingzcheung.xime.settings.LanguageSwitchPreferencesTest \
    com.kingzcheung.xime.keyboard.QuickActionLayoutTest \
    com.kingzcheung.xime.ui.render.ToolCabinRenderTest \
    com.kingzcheung.xime.ui.render.VerificationCodePermissionTest \
    com.kingzcheung.xime.ui.settings.CreditsTest \
    com.kingzcheung.xime.resources.CommercialAssetPackagingTest \
    com.kingzcheung.xime.association.AmericanEnglishSpellingTest \
    com.kingzcheung.xime.association.EnglishTypoCorrectionsTest \
    com.kingzcheung.xime.association.EnglishAssociationStartupTest \
    com.kingzcheung.xime.association.EnglishContractionCompletionTest \
    com.kingzcheung.xime.service.EnglishCompletionEditorTest \
    com.kingzcheung.xime.service.EnglishAutoSpaceTest \
    com.kingzcheung.xime.ui.render.LanTypeOfflineUiTest \
    com.kingzcheung.xime.ui.render.SettingsHomeRenderTest
fi
selectors=()
for test_class in "$@"; do selectors+=(--tests "$test_class"); done
exec ./gradlew :app:testDebugUnitTest -I scripts/test-runtime.init.gradle \
  --no-daemon --max-workers=1 \
  -Pkotlin.compiler.execution.strategy=in-process \
  '-Dorg.gradle.jvmargs=-Xmx4096m -Dfile.encoding=UTF-8' \
  "${selectors[@]}"
