package com.kingzcheung.xime.ui.settings

import android.content.res.AssetManager
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Licenses remain readable with airplane mode enabled; browsing source websites is optional. */
@Composable
internal fun LocalLicenseDocuments() {
    val assets = LocalContext.current.assets
    val documents by produceState<List<String>>(emptyList(), assets) {
        value = withContext(Dispatchers.IO) {
            listOf("NOTICE.txt") + licenseDocuments(assets, "licenses")
        }
    }
    var menu by remember { mutableStateOf(false) }
    var selected by remember { mutableStateOf<String?>(null) }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("随包许可 · 离线阅读", style = MaterialTheme.typography.titleMedium)
            Text("应用、引擎和资源的许可文本保存在安装包内，可以直接查看。",
                style = MaterialTheme.typography.bodyMedium)
            Box {
                OutlinedButton(onClick = { menu = true }, enabled = documents.isNotEmpty()) {
                    Text("选择许可文件")
                }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    documents.forEach { path ->
                        DropdownMenuItem(text = {
                            Text(if (path == "NOTICE.txt") "第三方资源与来源说明" else path.removePrefix("licenses/"))
                        }, onClick = { selected = path; menu = false })
                    }
                }
            }
        }
    }
    selected?.let { path ->
        val content by produceState<String?>(null, path, assets) {
            value = withContext(Dispatchers.IO) {
                runCatching { assets.open(path).bufferedReader(Charsets.UTF_8).use { it.readText() } }
                    .getOrElse { "此文件未包含在当前安装包中，请核对同版本源码和发行说明。" }
            }
        }
        AlertDialog(
            onDismissRequest = { selected = null },
            title = { Text(path.substringAfterLast('/')) },
            text = {
                SelectionContainer {
                    Column(Modifier.heightIn(max = 440.dp).verticalScroll(rememberScrollState())) {
                        Text(content ?: "正在打开…", style = MaterialTheme.typography.bodySmall)
                    }
                }
            },
            confirmButton = { TextButton(onClick = { selected = null }) { Text("关闭") } }
        )
    }
}

private fun licenseDocuments(assets: AssetManager, folder: String, depth: Int = 0): List<String> {
    if (depth > 8) return emptyList()
    return runCatching {
        assets.list(folder).orEmpty().sorted().flatMap { name ->
            val path = "$folder/$name"
            if (assets.list(path).isNullOrEmpty()) listOf(path)
            else licenseDocuments(assets, path, depth + 1)
        }
    }.getOrDefault(emptyList())
}
