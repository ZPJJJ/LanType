package com.kingzcheung.xime.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.automirrored.twotone.OpenInNew
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material.icons.filled.Code
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PrivacyTip
import androidx.compose.material.icons.twotone.BugReport
import androidx.compose.material.icons.twotone.Code
import androidx.compose.material.icons.twotone.Description
import androidx.compose.material.icons.twotone.EmojiEmotions
import androidx.compose.material.icons.twotone.Favorite
import androidx.compose.material.icons.twotone.NewReleases
import androidx.compose.material.icons.twotone.PersonOutline
import androidx.compose.material.icons.twotone.PrivacyTip
import androidx.compose.material.icons.twotone.Storage
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kingzcheung.xime.BuildConfig
import com.kingzcheung.xime.settings.SettingsPreferences
import com.kingzcheung.xime.ui.theme.MaterialLevel
import com.kingzcheung.xime.ui.theme.VisualStyles
import com.kingzcheung.xime.ui.theme.visualMaterial
import com.kingzcheung.xime.model.DownloadMirrors
import com.kingzcheung.xime.update.AppUpdateCatalog
import com.kingzcheung.xime.util.FileLogger
import com.kingzcheung.xime.platform.AndroidPlatform

data class LicenseItem(
    val name: String,
    val license: String,
    val url: String
)

object AppInfo {
    val versionName: String = BuildConfig.VERSION_NAME
    val versionCode: Int = BuildConfig.VERSION_CODE
    val gitHash: String = BuildConfig.GIT_HASH
    
    val androidVersion: String = AndroidPlatform.versionLabel
    val deviceModel: String = AndroidPlatform.deviceLabel
    
    val dependencies = listOf(
        LicenseItem(
            name = "CyIME · 上游项目，由 Cyletix 维护开发",
            license = "GPL-3.0",
            url = "https://github.com/Cyletix/CyIME/blob/main/LICENSE"
        ),
        LicenseItem(
            name = "librime",
            license = "BSD-3-Clause",
            url = "https://github.com/rime/librime"
        ),
        LicenseItem(
            name = "AndroidX Core",
            license = "Apache-2.0",
            url = "https://developer.android.com/jetpack/androidx"
        ),
        LicenseItem(
            name = "Jetpack Compose",
            license = "Apache-2.0",
            url = "https://developer.android.com/jetpack/compose"
        ),
        LicenseItem(
            name = "Material Design Icons",
            license = "Apache-2.0",
            url = "https://fonts.google.com/icons"
        ),
        LicenseItem(
            name = "Kotlin",
            license = "Apache-2.0",
            url = "https://kotlinlang.org"
        ),
        LicenseItem(
            name = "Navigation Compose",
            license = "Apache-2.0",
            url = "https://developer.android.com/jetpack/compose/navigation"
        ),
        LicenseItem(
            name = "Lifecycle",
            license = "Apache-2.0",
            url = "https://developer.android.com/jetpack/androidx/releases/lifecycle"
        ),
        LicenseItem(
            name = "Boost",
            license = "BSL-1.0",
            url = "https://www.boost.org"
        ),
        LicenseItem(
            name = "OpenCC (Open Chinese Convert)",
            license = "Apache-2.0",
            url = "https://github.com/BYVoid/OpenCC"
        ),
        LicenseItem(
            name = "KaTeX",
            license = "MIT",
            url = "https://github.com/KaTeX/KaTeX"
        ),
        LicenseItem(
            name = "Xime(CyIME 基于它开发)",
            license = "GPL-3.0",
            url = "https://github.com/ximeiorg/Xime"
        )
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AboutContent(
    onBack: () -> Unit,
    onNavigateToPrivacy: () -> Unit,
    onNavigateToLicenses: () -> Unit,
    onNavigateToCredits: () -> Unit = {},
    onNavigateToReleaseNotes: () -> Unit = {},
    onNavigateToLogViewer: () -> Unit = {},
    onNavigateToHandwritingCapture: () -> Unit = {},
    onNavigateToStorageSpace: () -> Unit = {},
) {
    val uriHandler = LocalUriHandler.current
    val context = LocalContext.current
    var verboseLoggingEnabled by remember {
        mutableStateOf(SettingsPreferences.isVerboseLoggingEnabled(context))
    }
    var launchAdEgg by remember { mutableStateOf(SettingsPreferences.isLaunchAdEggEnabled(context)) }
    
    Scaffold(
        containerColor = MaterialTheme.colorScheme.surface,
        topBar = {
            TopAppBar(
                title = { Text("关于") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "返回"
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                    titleContentColor = MaterialTheme.colorScheme.onSurface
                )
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .settingsVerticalScroll()
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // App 信息
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .visualMaterial(VisualStyles.current, 12.dp, level = MaterialLevel.RAISED)
                            .padding(16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = "澜语输入法 · 离线版",
                            fontSize = 28.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.primary
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "中文与美式英文的纯离线输入法。基于 Cyletix/CyIME 1.15.94 与 Rime，保留原作者版权，以 GNU GPLv3 提供源码。内置拼音、英文补全和滑行词库，以及离线语音、中文手写、图片识字模型。词库、设置、剪贴板和个性化数据留在本机；扩展资源通过本地文件导入。",
                            fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            text = "版本 ${AppInfo.versionName} (${AppInfo.versionCode})",
                            fontSize = 14.sp,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = "构建: ${AppInfo.gitHash}",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                // 国内打开魔搭上的同一份安装包，海外打开 GitHub 发布页。
                                .clickable { onNavigateToReleaseNotes() },
                            horizontalArrangement = Arrangement.Center,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.OpenInNew,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                                tint = MaterialTheme.colorScheme.primary
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = "本版本功能与说明",
                                fontSize = 14.sp,
                                color = MaterialTheme.colorScheme.primary
                            )
                        }
                    }
                }
            
            // 作者与源代码使用同一种完整卡片。
                AboutLinkCard(
                    title = "上游作者 · Cyletix",
                    subtitle = "github.com/Cyletix",
                    icon = Icons.TwoTone.PersonOutline,
                    onClick = { uriHandler.openUri("https://github.com/Cyletix") },
                )
                AboutLinkCard(
                    title = "上游 CyIME 源代码（本版源码另附）",
                    subtitle = "github.com/Cyletix/CyIME",
                    icon = Icons.TwoTone.Code,
                    onClick = { uriHandler.openUri("https://github.com/Cyletix/CyIME") },
                )

                AppUpdateSection()

            // 链接项
                SettingsSection(title = "信息与工具") {
                        // 安装包里带的各版发布说明，不联网。
                        SettingsItem(
                            icon = Icons.TwoTone.NewReleases,
                            title = "更新内容",
                            onClick = onNavigateToReleaseNotes
                        )
                        HorizontalDivider(
                            modifier = Modifier.padding(start = 56.dp),
                            thickness = 0.5.dp,
                            color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
                        )
                        SettingsItem(
                            icon = Icons.TwoTone.Favorite,
                            title = "鸣谢",
                            onClick = onNavigateToCredits
                        )
                        HorizontalDivider(
                            modifier = Modifier.padding(start = 56.dp),
                            thickness = 0.5.dp,
                            color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
                        )
                        SettingsItem(
                            icon = Icons.TwoTone.PrivacyTip,
                            title = "隐私策略",
                            onClick = onNavigateToPrivacy
                        )
                        HorizontalDivider(
                            modifier = Modifier.padding(start = 56.dp),
                            thickness = 0.5.dp,
                            color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
                        )
                        SettingsItem(
                            icon = Icons.TwoTone.Description,
                            title = "开源许可证",
                            onClick = onNavigateToLicenses
                        )
                        HorizontalDivider(
                            modifier = Modifier.padding(start = 56.dp),
                            thickness = 0.5.dp,
                            color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
                        )
                        // 使用文档从设置首页收到这里（内容较旧，少有人点）。
                        SettingsItem(
                            icon = Icons.TwoTone.Description,
                            title = "使用文档",
                            onClick = { uriHandler.openUri("https://github.com/Cyletix/CyIME/blob/main/docs/usage.md") }
                        )
                        HorizontalDivider(
                            modifier = Modifier.padding(start = 56.dp),
                            thickness = 0.5.dp,
                            color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
                        )
                        SettingsItem(
                            icon = Icons.TwoTone.BugReport,
                            title = "日志查看器",
                            onClick = onNavigateToLogViewer
                        )
                        HorizontalDivider(
                            modifier = Modifier.padding(start = 56.dp),
                            thickness = 0.5.dp,
                            color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
                        )
                        SettingsItem(
                            icon = Icons.TwoTone.Storage,
                            title = "存储空间",
                            onClick = onNavigateToStorageSpace
                        )
                        // 彩蛋（用户 11-15）：默认关；老人包不放。刚打开时马上放一遍。
                        if (false) {
                            HorizontalDivider(
                                modifier = Modifier.padding(start = 56.dp),
                                thickness = 0.5.dp,
                                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
                            )
                            SettingsToggleItem(
                                icon = Icons.TwoTone.EmojiEmotions,
                                title = "启动广告（彩蛋）",
                                subtitle = "每次打开设置先看 5 秒假广告，可以跳过。画着玩的，不联网。",
                                checked = launchAdEgg,
                                onCheckedChange = { enabled ->
                                    launchAdEgg = enabled
                                    SettingsPreferences.setLaunchAdEggEnabled(context, enabled)
                                    if (enabled) LaunchAdEgg.preview()
                                }
                            )
                        }
                        if (BuildConfig.DEBUG) {
                            HorizontalDivider(
                                modifier = Modifier.padding(start = 56.dp),
                                thickness = 0.5.dp,
                                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
                            )
                            SettingsItem(
                                icon = Icons.TwoTone.BugReport,
                                title = "调试日志",
                                onClick = {},
                                trailing = {
                                    Switch(
                                        checked = verboseLoggingEnabled,
                                        onCheckedChange = { enabled ->
                                            verboseLoggingEnabled = enabled
                                            SettingsPreferences.setVerboseLoggingEnabled(context, enabled)
                                            FileLogger.setVerboseLoggingEnabled(enabled)
                                        }
                                    )
                                }
                            )
                        }
                }
            
            // 设备信息
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .visualMaterial(VisualStyles.current, 12.dp, level = MaterialLevel.RAISED)
                            .padding(16.dp)
                    ) {
                        Text(
                            text = "设备信息",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        InfoRow(label = "系统版本", value = AppInfo.androidVersion)
                        InfoRow(label = "设备型号", value = AppInfo.deviceModel)
                    }
                }
        }
    }
}

@Composable
private fun SettingsItem(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    onClick: () -> Unit,
    trailing: (@Composable () -> Unit)? = null
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(16.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(40.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(22.dp)
            )
        }
        Spacer(modifier = Modifier.width(16.dp))
        Text(
            text = title,
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.weight(1f)
        )
        if (trailing != null) {
            trailing()
        } else {
            Icon(
                imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurface
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PrivacyPolicyContent(
    onBack: () -> Unit
) {
    Scaffold(
        containerColor = MaterialTheme.colorScheme.surface,
        topBar = {
            TopAppBar(
                title = { Text("隐私策略") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "返回"
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                    titleContentColor = MaterialTheme.colorScheme.onSurface
                )
            )
        }
    ) { paddingValues ->
        val listState = rememberLazyListState()
        LazyColumn(
            state = listState,
            modifier = Modifier.settingsGutterScroll(listState)
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 16.dp)
        ) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                ) {
                    Column(
                        modifier = Modifier
                            .visualMaterial(VisualStyles.current, 12.dp, level = MaterialLevel.RAISED)
                            .padding(16.dp)
                    ) {
                        Text(
                            text = "澜语输入法隐私说明",
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        
                        PrivacySection(
                            title = "数据收集",
                            content = "本版不具备联网权限，不上传输入内容、录音、笔迹或使用数据。中文、英文候选和随包语音、手写、图片识字模型在手机上处理。系统和接收文字的目标应用有各自的数据处理方式。"
                        )
                        
                        PrivacySection(
                            title = "本地存储",
                            content = "设置、用户词库、词频和剪贴板记录保存在应用私有目录。可在应用中删除数据，或通过备份功能导出到您选择的本地文件。系统云备份已关闭。"
                        )
                        
                        PrivacySection(
                            title = "网络权限",
                            content = "本版本移除了 INTERNET 权限。在线语音、云端 AI、云同步、在线商店和自动更新不可用。核心模型随安装包提供，扩展词库或模型可通过本地文件导入。"
                        )
                        PrivacySection(
                            title = "按需权限",
                            content = "本版不申请短信或通讯录权限。麦克风用于您主动开启的本地语音输入；相机和所选图片用于本地识字。您可以拒绝或撤回这些权限，继续使用普通键盘。"
                        )
                        PrivacySection(
                            title = "工具舱",
                            content = "单位换算、文本转换和动态模板都在本机运行。只有您点击读取选区或确认使用剪贴板时，工具才取得相应内容；结果先预览，再由您决定是否写入当前输入框。临时文本不会自动保存，主动点击保存模板时才保留模板原文。脱敏只匹配常见格式，请在发送前检查结果。"
                        )
                        
                        PrivacySection(
                            title = "输入内容",
                            content = "密码输入框不提供英文候选、不学习输入内容；遵循宿主的无个性化学习和禁用候选标志。普通输入的个性化词频只在本机保存，可以手动开启无痕模式。"
                        )
                        
                        PrivacySection(
                            title = "剪贴板",
                            content = "剪贴板历史只保存在本机，可置顶、删除或清空。系统标记为敏感的条目依照敏感内容规则处理。剪贴板网络同步在本版不可用。"
                        )
                        
                        PrivacySection(
                            title = "开源",
                            content = "本版本应用源码与构建说明随安装包另附，遵循 GPLv3。关于页的 GitHub 链接用于注明上游来源，在外部浏览器打开；本应用本身不会联网。第三方词库与模型许可见开源许可证。本版不是 CyIME 官方发行版。"
                        )
                        
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            text = "更新日期：2026年11月17日",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PrivacySection(title: String, content: String) {
    Column(modifier = Modifier.padding(vertical = 8.dp)) {
        Text(
            text = title,
            fontSize = 16.sp,
            fontWeight = FontWeight.Medium
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = content,
            fontSize = 14.sp,
            color = MaterialTheme.colorScheme.onSurface,
            lineHeight = 20.sp
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LicensesContent(
    onBack: () -> Unit
) {
    val uriHandler = LocalUriHandler.current
    
    Scaffold(
        containerColor = MaterialTheme.colorScheme.surface,
        topBar = {
            TopAppBar(
                title = { Text("开源许可证") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "返回"
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                    titleContentColor = MaterialTheme.colorScheme.onSurface
                )
            )
        }
    ) { paddingValues ->
        val listState = rememberLazyListState()
        LazyColumn(
            state = listState,
            modifier = Modifier.settingsGutterScroll(listState)
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item { LocalLicenseDocuments() }
            item {
                Text("项目来源（在外部浏览器打开）", style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            items(AppInfo.dependencies) { item ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            uriHandler.openUri(item.url)
                        },
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                ) {
                    Column(
                        modifier = Modifier
                            .visualMaterial(VisualStyles.current, 12.dp, level = MaterialLevel.RAISED)
                            .padding(16.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = item.name,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Medium
                            )
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.OpenInNew,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = item.license,
                            fontSize = 14.sp,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                }
            }
        }
    }
}
@Composable
private fun AboutLinkCard(title: String, subtitle: String, icon: ImageVector, onClick: () -> Unit) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth()
                .visualMaterial(VisualStyles.current, 12.dp, level = MaterialLevel.RAISED)
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier.size(40.dp).clip(RoundedCornerShape(10.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(22.dp))
            }
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.width(12.dp))
            Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(18.dp))
        }
    }
}
