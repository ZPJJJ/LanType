package com.kingzcheung.xime.ui.settings

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.kingzcheung.xime.settings.SettingsPreferences

/** The commercial offline build does not register an SMS receiver or request SMS access. */
@Composable
internal fun VerificationCodeSettings() {
    val context = LocalContext.current
    LaunchedEffect(context) {
        // An upgrade or imported settings backup must not reactivate the retired SMS path.
        SettingsPreferences.setSmsCodeEnabled(context, false)
        SettingsPreferences.setSmsCodeSyncEnabled(context, false)
    }
    VerificationCodeSettingsCard(false, false, onToggle = {})
}

/** Kept for compatibility with the unbundled upstream relay code. */
internal fun verificationCodeSendLock(smsCodeOn: Boolean, syncOn: Boolean): String? = when {
    !smsCodeOn -> "需先打开「新短信验证码自动复制」"
    !syncOn -> "需先打开上面的「同步剪贴板」"
    else -> null
}

@Suppress("UNUSED_PARAMETER")
@Composable
internal fun VerificationCodeSettingsCard(
    enabled: Boolean, denied: Boolean,
    sendToDevices: Boolean = false, sendLock: String? = null,
    onSendToDevices: (Boolean) -> Unit = {}, onToggle: (Boolean) -> Unit
) {
    SettingsSection(title = "验证码") {
        Text(
            "澜语不读取短信。请在短信应用或系统通知中复制验证码，再通过键盘粘贴。",
            modifier = Modifier.padding(16.dp),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
