package com.kingzcheung.xime.ui.settings

import android.widget.Toast
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import com.kingzcheung.xime.contacts.ContactSuggestions

/**
 * LanType does not request address-book access. Keep local plugin management usable,
 * but never start a permission flow for a contacts plugin, including an imported one.
 */
@Composable
internal fun rememberContactsPermissionGate(pluginId: String): (Boolean, () -> Unit) -> Unit {
    val context = LocalContext.current
    return { turnOn, proceed ->
        if (!turnOn || !ContactSuggestions.isContactsPlugin(pluginId)) proceed()
        else Toast.makeText(context, CONTACTS_DENIED, Toast.LENGTH_LONG).show()
    }
}

internal const val CONTACTS_DENIED = "澜语不读取通讯录，此插件无法启用。常用内容可手动保存到常用语。"
