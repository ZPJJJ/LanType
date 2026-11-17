package com.kingzcheung.xime.ui.render

import android.app.Application
import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.activity.ComponentActivity
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.Lifecycle
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.kingzcheung.xime.settings.SettingsPreferences
import com.kingzcheung.xime.ui.settings.VerificationCodeSettings
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

@RunWith(AndroidJUnit4::class)
@Config(sdk = [34], application = Application::class, qualifiers = "zh-rCN-w360dp-h400dp-mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class VerificationCodePermissionTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun commercialBuildOffersManualPasteWithoutRequestingSmsEvenAfterLegacyRestore() {
        val app = rule.activity.application
        SettingsPreferences.setSmsCodeEnabled(app, true)
        SettingsPreferences.setSmsCodeSyncEnabled(app, true)
        rule.setContent { MaterialTheme { VerificationCodeSettings() } }
        rule.onNodeWithText("澜语不读取短信", substring = true).assertIsDisplayed()
        rule.onAllNodes(isToggleable()).assertCountEquals(0)
        rule.runOnIdle {
            assertFalse(SettingsPreferences.isSmsCodeEnabled(app))
            assertFalse(SettingsPreferences.isSmsCodeSyncEnabled(app))
            assertNull(shadowOf(rule.activity).lastRequestedPermission)
        }
        rule.activityRule.scenario.moveToState(Lifecycle.State.CREATED)
        rule.activityRule.scenario.moveToState(Lifecycle.State.RESUMED)
        rule.onAllNodes(isToggleable()).assertCountEquals(0)
        rule.runOnIdle { assertNull(shadowOf(rule.activity).lastRequestedPermission) }
        saveImage()
    }

    private fun saveImage() {
        val out = System.getenv("CYIME_RENDER_OUT") ?: return
        val root = rule.activity.window.decorView
        val image = Bitmap.createBitmap(root.width, root.height, Bitmap.Config.ARGB_8888)
        rule.runOnIdle { root.draw(Canvas(image)) }
        File(out, "sms-manual-paste.png").outputStream().use { image.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }
}
