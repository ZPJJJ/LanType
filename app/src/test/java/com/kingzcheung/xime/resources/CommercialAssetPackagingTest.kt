package com.kingzcheung.xime.resources

import android.app.Application
import com.kingzcheung.xime.association.BaseAssociationModel
import com.kingzcheung.xime.association.TrieAssociationEngine
import com.kingzcheung.xime.handwriting.HandwritingEngine
import com.kingzcheung.xime.settings.InputLanguage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

/** Exercises AssetManager after AAPT packaging, not raw source-directory files. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = Application::class)
class CommercialAssetPackagingTest {
    private val context get() = RuntimeEnvironment.getApplication()

    @Test fun packagedStrokeTemplatesLoadThroughTheProductionEngine() = runBlocking {
        assertTrue(HandwritingEngine.hasModel(context))
        withContext(Dispatchers.IO) {
            try {
                assertTrue(HandwritingEngine.initialize(context))
                val result = HandwritingEngine.predict(listOf(listOf(10f to 50f, 50f to 49f, 90f to 50f)), language = InputLanguage.CHINESE)
                assertEquals("一", result.firstOrNull()?.char)
            } finally { HandwritingEngine.release() }
        }
    }

    @Test fun originalAssociationTablesAreReadableByTheirRuntimeNames() {
        val marks = context.assets.open(BaseAssociationModel.WORD_COMPLETIONS_ASSET).reader(Charsets.UTF_8)
            .use(BaseAssociationModel::readWordCompletions)
        val model = context.assets.open(BaseAssociationModel.ASSET).reader(Charsets.UTF_8)
            .use { BaseAssociationModel.readWithWordCompletions(it, marks) }
        assertTrue(model.predict("谢谢").any { it.text == "你" })
        assertTrue(model.predict("生日").any { it.text == "快乐" })
    }

    @Test fun fullScowlBinarySupportsEnglishCompletion() = runBlocking {
        val engine = TrieAssociationEngine()
        try {
            assertTrue(engine.initialize(context))
            assertTrue(engine.predict("keyb", 10).any { it.text == "keyboard" })
            assertTrue(engine.predict("colo", 10).any { it.text == "color" })
        } finally { engine.release() }
    }
}
