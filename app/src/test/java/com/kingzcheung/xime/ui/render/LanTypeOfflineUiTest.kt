package com.kingzcheung.xime.ui.render

import android.app.Application
import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.activity.ComponentActivity
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.kingzcheung.xime.ui.settings.OfflineResourcesContent
import com.kingzcheung.xime.ui.settings.SetupStatus
import com.kingzcheung.xime.ui.settings.SetupWizardContent
import com.kingzcheung.xime.ui.theme.XimeTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/** Real Compose rendering with an isolated Application; this does not execute ARM64 IME engines. */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [34], application = Application::class, qualifiers = "w360dp-h800dp-xhdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class LanTypeOfflineUiTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    private fun capture(name: String) {
        val out = System.getenv("CYIME_RENDER_OUT") ?: return
        rule.waitForIdle()
        val view = rule.activity.window.decorView
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        rule.runOnIdle { view.draw(Canvas(bitmap)) }
        val file = File(out, "$name.png")
        file.parentFile!!.mkdirs()
        file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
    }

    @Test fun localResourcesRemainReachableOnANarrowPhone() {
        val routes = mutableListOf<String>()
        val dark = mutableStateOf(false)
        rule.setContent {
            XimeTheme(darkTheme = dark.value) {
                OfflineResourcesContent(
                    onBack = { routes += "back" },
                    onOpenLanguages = { routes += "languages" },
                    onOpenSchemes = { routes += "schemes" },
                    onOpenDictionaries = { routes += "dictionaries" },
                    onOpenModels = { routes += "models" },
                    onOpenPlugins = { routes += "plugins" },
                )
            }
        }
        rule.onNodeWithText("中文与英文(美国)").assertIsDisplayed()
        capture("lantype-local-resources-light")
        for ((label, route) in listOf(
            "中文与英文(美国)" to "languages",
            "本地输入方案" to "schemes",
            "本地词库" to "dictionaries",
            "本地模型" to "models",
            "本地插件" to "plugins",
        )) {
            rule.onNodeWithText(label).performScrollTo().assertIsDisplayed().performClick()
            rule.runOnIdle { assertEquals(route, routes.last()) }
        }
        rule.onNodeWithText("下载模型").assertDoesNotExist()
        rule.onNodeWithText("在线商店").assertDoesNotExist()
        rule.onNodeWithText("中文与英文(美国)").performScrollTo()
        rule.runOnIdle { dark.value = true }
        capture("lantype-local-resources-dark")
        assertEquals(listOf("languages", "schemes", "dictionaries", "models", "plugins"), routes)
    }

    @Test fun setupRequiresEnabledPreparedAndSelectedIme() {
        val status = mutableStateOf(SetupStatus(preparing = false, schemas = listOf("中文全拼", "英文(美国)")))
        var finished = 0
        rule.setContent {
            XimeTheme(darkTheme = false) {
                SetupWizardContent(status.value, onEnable = {}, onSchemas = {}, onRetry = {},
                    onSwitch = {}, onFinish = { finished++ })
            }
        }
        capture("lantype-setup")
        rule.onNodeWithText("选择 澜语输入法").performScrollTo().assertIsNotEnabled()
        rule.onNodeWithText("完成三项后即可开始使用").performScrollTo().assertIsNotEnabled()
        rule.runOnIdle { status.value = status.value.copy(imeEnabled = true) }
        rule.onNodeWithText("选择 澜语输入法").performScrollTo().assertIsEnabled()
        rule.onNodeWithText("完成三项后即可开始使用").performScrollTo().assertIsNotEnabled()
        rule.runOnIdle { status.value = status.value.copy(imeSelected = true, preparing = true) }
        rule.onNodeWithText("完成三项后即可开始使用").assertIsNotEnabled()
        rule.runOnIdle { status.value = status.value.copy(preparing = false) }
        rule.onNodeWithText("开始使用").performScrollTo().assertIsEnabled().performClick()
        rule.runOnIdle { assertEquals(1, finished) }
        capture("lantype-setup-ready")
    }
}
