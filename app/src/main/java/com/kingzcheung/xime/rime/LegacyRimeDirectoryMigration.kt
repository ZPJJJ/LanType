package com.kingzcheung.xime.rime

import java.io.File

/** Moves legacy entries without merging databases, overwriting conflicts, or deleting unmoved data. */
internal object LegacyRimeDirectoryMigration {
    fun moveMissingEntries(
        source: File,
        destination: File,
        rename: (File, File) -> Boolean = { from, to -> from.renameTo(to) },
    ): Boolean {
        if (!source.exists()) return true
        if (!destination.exists()) return rename(source, destination)
        val entries = source.listFiles() ?: return false
        entries.forEach { entry ->
            val target = File(destination, entry.name)
            if (!target.exists()) rename(entry, target)
        }
        // File.delete succeeds only when the directory is empty. Conflicts and failed
        // renames stay at their original paths, including complete LevelDB directories.
        return source.delete()
    }
}
