package com.kingzcheung.xime.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.kingzcheung.xime.ui.settings.VerificationCodeSettingsCard
import org.junit.Rule
import org.junit.Test

class VerificationCodeLayoutTest {
    @get:Rule val rule = createComposeRule()
    private data class Viewport(val width: Int, val font: Float)

    @Test fun manualPasteExplanationFitsNarrowAndLargeFontLayouts() {
        val viewport = mutableStateOf(Viewport(280, 2f))
        rule.setContent {
            val v = viewport.value
            CompositionLocalProvider(LocalDensity provides Density(1f, v.font)) {
                MaterialTheme {
                    Column(Modifier.requiredSize(v.width.dp, 360.dp).testTag("otp-settings-host")
                        .verticalScroll(rememberScrollState())) {
                        VerificationCodeSettingsCard(false, denied = false) {}
                    }
                }
            }
        }
        for (v in listOf(Viewport(240, 2f), Viewport(280, 2f), Viewport(360, 1f))) {
            rule.runOnIdle { viewport.value = v }
            rule.onNodeWithText("澜语不读取短信", substring = true).performScrollTo().assertIsDisplayed()
            rule.onAllNodes(isToggleable()).assertCountEquals(0)
            rule.assertGeometry("otp-settings-host", "手动验证码说明 $v")
        }
    }
}
