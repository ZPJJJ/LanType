package com.kingzcheung.xime.security

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** 设置每次打开时，装的不是作者签名的包就弹这一框；点哪个按钮都只关这一次。 */
@Composable
fun InstallIntegrityWarning() {
    val context = LocalContext.current.applicationContext
    val result by produceState<InstallIntegrity.Result?>(null) {
        value = withContext(Dispatchers.IO) { InstallIntegrity.check(context) }
    }
    var dismissed by rememberSaveable { mutableStateOf(false) }
    if (result != InstallIntegrity.Result.FOREIGN || dismissed) return
    val uriHandler = LocalUriHandler.current
    AlertDialog(
        onDismissRequest = { dismissed = true },
        properties = DialogProperties(dismissOnClickOutside = false),
        title = { Text("安装包签名不同") },
        text = { Text("这个安装包与澜语输入法本次交付的签名不同。如果是您自行编译，这是正常的；否则请核对安装包来源。澜语是基于 CyIME 的独立开源修改版，不能用 CyIME 官方包覆盖更新。") },
        confirmButton = {
            TextButton(onClick = {
                dismissed = true
            }) { Text("关闭") }
        },
        dismissButton = {
            TextButton(onClick = { dismissed = true }) { Text("知道了") }
        },
    )
}
