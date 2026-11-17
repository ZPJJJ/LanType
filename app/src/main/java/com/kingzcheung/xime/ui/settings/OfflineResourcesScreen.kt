package com.kingzcheung.xime.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Extension
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp

/** Local resources only: entering this page never instantiates a marketplace. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun OfflineResourcesContent(
    onBack: () -> Unit,
    onOpenLanguages: () -> Unit,
    onOpenSchemes: () -> Unit,
    onOpenDictionaries: () -> Unit,
    onOpenModels: () -> Unit,
    onOpenPlugins: () -> Unit,
) {
    Scaffold(topBar = {
        TopAppBar(title = { Text("本地资源") }, navigationIcon = {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") }
        })
    }) { padding ->
        LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).testTag("offline-resources"),
            contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            item {
                Text("使用随包资源，也可从手机文件导入自己的词库、模型和插件。",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            item {
                SettingsSection(title = "输入与词库") {
                    SettingsItem(Icons.Default.Info, "中文与英文(美国)", "选择输入语言、拼音方案和键盘布局", onClick = onOpenLanguages)
                    SettingsItem(Icons.Default.Info, "本地输入方案", "管理已安装方案，或导入方案文件", onClick = onOpenSchemes)
                    SettingsItem(Icons.Default.Info, "本地词库", "管理个人词语、常用短语和分类词库", onClick = onOpenDictionaries)
                }
            }
            item {
                SettingsSection(title = "模型与插件") {
                    SettingsItem(Icons.Default.GraphicEq, "本地模型", "查看已安装模型，或从文件、文件夹导入", onClick = onOpenModels)
                    SettingsItem(Icons.Default.Extension, "本地插件", "管理已安装插件，或从文件安装", onClick = onOpenPlugins)
                }
            }
            item {
                Text("翻译等扩展能力需要对应的本地模型；未安装模型时不会启用。",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}
