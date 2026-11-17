package com.kingzcheung.xime.model

import android.content.Context

/** Offline model version helpers. Network updates are unavailable in LanType.
 * Version comparison is retained for installing bundled upgrades and local imports. */
object ModelAutoUpdater {
    private const val PREFS = "model_auto_update"
    private const val KEY_ENABLED = "enabled"
    private const val PIN_PREFIX = "pinned_"
    private const val ATTEMPT_PREFIX = "attempt_"

    /** 同一个新版本最多自动试几次；之后只在模型中心手动更新。 */
    internal const val MAX_ATTEMPTS = 3
    /** 两次自动尝试同一个新版本至少隔多久。 */
    internal const val RETRY_INTERVAL_MS = 6 * 60 * 60 * 1000L
    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    @Suppress("UNUSED_PARAMETER")
    fun isEnabled(context: Context): Boolean = false

    @Suppress("UNUSED_PARAMETER")
    fun setEnabled(context: Context, enabled: Boolean) {
        // Discard a restored or legacy true value; it cannot enable networking.
        prefs(context).edit().putBoolean(KEY_ENABLED, false).apply()
    }

    /** 模型目录里可下载的最新版本（目录里第一个没退役的）。 */
    internal fun latestVersion(model: ModelInfo): ModelVersion? = model.downloadableVersions.firstOrNull()

    /** [candidate] 比 [installed] 新：目录里越靠前越新；认不出的版本不算更新的。 */
    internal fun isNewer(model: ModelInfo, candidate: ModelVersion, installed: ModelVersion): Boolean {
        val c = model.versions.indexOfFirst { it.version == candidate.version }
        val i = model.versions.indexOfFirst { it.version == installed.version }
        return c >= 0 && i >= 0 && c < i
    }

    /** 该自动换成的版本；不用换时返回 null。[pinned] 是用户特意装的版本。 */
    internal fun pendingUpdate(model: ModelInfo, installed: ModelVersion?, pinned: String?): ModelVersion? {
        installed ?: return null
        val latest = latestVersion(model) ?: return null
        if (pinned != null && pinned == installed.version) return null
        return latest.takeIf { isNewer(model, it, installed) }
    }

    /** 这个新版本还能不能自动试：没试过、或试过不到 [MAX_ATTEMPTS] 次且离上次超过 [RETRY_INTERVAL_MS]。 */
    internal fun attemptAllowed(record: String?, version: String, now: Long): Boolean {
        val parts = record?.split('|') ?: return true
        if (parts.size != 3 || parts[0] != version) return true
        val count = parts[1].toIntOrNull() ?: return true
        val last = parts[2].toLongOrNull() ?: return true
        // 时钟被往回调过时不卡住。
        return count < MAX_ATTEMPTS && (now - last >= RETRY_INTERVAL_MS || now < last)
    }

    internal fun nextAttempt(record: String?, version: String, now: Long): String {
        val parts = record?.split('|')
        val count = if (parts?.size == 3 && parts[0] == version) parts[1].toIntOrNull() ?: 0 else 0
        return "$version|${count + 1}|$now"
    }

    fun pinnedVersion(context: Context, id: String): String? = prefs(context).getString(PIN_PREFIX + id, null)

    /** 用户在模型中心装好了 [version]：不是最新版就固定在这个版本、不自动换；装的是最新版就解除。 */
    fun onUserInstalled(context: Context, model: ModelInfo, version: ModelVersion?) {
        val editor = prefs(context).edit().remove(ATTEMPT_PREFIX + model.id)
        val latest = latestVersion(model)
        if (version == null || latest == null || version.version == latest.version) editor.remove(PIN_PREFIX + model.id)
        else editor.putString(PIN_PREFIX + model.id, version.version)
        editor.apply()
    }

    fun onUserDeleted(context: Context, id: String) {
        prefs(context).edit().remove(PIN_PREFIX + id).remove(ATTEMPT_PREFIX + id).apply()
    }

    /** 模型管理里旧版本后面的一句说明。 */
    fun updateNote(context: Context, model: ModelInfo, installedVersion: String?): String? {
        val latest = latestVersion(model) ?: return null
        val installed = model.versions.firstOrNull { it.version == installedVersion } ?: return null
        if (!isNewer(model, latest, installed)) return null
        return "目录中有新版 ${latest.version}，本版仅支持从本地导入，不联网更新"
    }

    /** Compatibility entry point. No worker, network check, retry or download is created. */
    @Suppress("UNUSED_PARAMETER")
    fun start(context: Context, force: Boolean = false) = Unit
}
