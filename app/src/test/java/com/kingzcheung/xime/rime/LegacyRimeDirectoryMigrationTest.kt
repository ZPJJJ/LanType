package com.kingzcheung.xime.rime

import com.kingzcheung.xime.settings.BackupPreferenceStore
import com.kingzcheung.xime.settings.BackupRestoreTransaction
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class LegacyRimeDirectoryMigrationTest {
    @get:Rule val temporaryFolder = TemporaryFolder()

    @Test fun absentLegacyDirectoriesLeaveTheFlatLayoutUnchanged() {
        val files = temporaryFolder.newFolder("flat")
        val current = write(files, "rime/lantype_pinyin.userdb/000001.ldb", byteArrayOf(0, 1, 127, -1))
        val before = current.readBytes()
        for (legacy in listOf("rime/user", "rime/shared", "rime/market")) {
            val destination = if (legacy.endsWith("market")) File(files, "market") else File(files, "rime")
            assertTrue(LegacyRimeDirectoryMigration.moveMissingEntries(File(files, legacy), destination))
        }
        assertArrayEquals(before, current.readBytes())
        assertFalse(File(files, "market").exists())
    }

    @Test fun newDestinationReceivesTheWholeLegacyDirectoryUnchanged() {
        val files = temporaryFolder.newFolder("whole")
        val bytes = byteArrayOf(-128, 0, 42, 127)
        write(files, "rime/market/personal/words.dict.yaml", bytes)

        assertTrue(LegacyRimeDirectoryMigration.moveMissingEntries(File(files, "rime/market"), File(files, "market")))
        assertArrayEquals(bytes, File(files, "market/personal/words.dict.yaml").readBytes())
        assertFalse(File(files, "rime/market").exists())
    }

    @Test fun existingDestinationKeepsConflictingFilesAndWholeDatabasesAtTheirOriginalPaths() {
        val files = temporaryFolder.newFolder("conflicts")
        val oldCustom = byteArrayOf(0, 3, -1)
        val currentCustom = byteArrayOf(8, 2, 1)
        val oldDatabase = byteArrayOf(-5, 0, 4)
        val currentDatabase = byteArrayOf(2, -7, 3)
        val movable = byteArrayOf(6, 9, -128)
        write(files, "rime/user/default.custom.yaml", oldCustom)
        write(files, "rime/default.custom.yaml", currentCustom)
        write(files, "rime/user/lantype_pinyin.userdb/000001.ldb", oldDatabase)
        write(files, "rime/lantype_pinyin.userdb/CURRENT", currentDatabase)
        write(files, "rime/user/personal.dict.yaml", movable)

        assertFalse(LegacyRimeDirectoryMigration.moveMissingEntries(File(files, "rime/user"), File(files, "rime")))
        assertArrayEquals(oldCustom, File(files, "rime/user/default.custom.yaml").readBytes())
        assertArrayEquals(currentCustom, File(files, "rime/default.custom.yaml").readBytes())
        assertArrayEquals(oldDatabase, File(files, "rime/user/lantype_pinyin.userdb/000001.ldb").readBytes())
        assertArrayEquals(currentDatabase, File(files, "rime/lantype_pinyin.userdb/CURRENT").readBytes())
        assertFalse("LevelDB files from two databases must never be mixed", File(files, "rime/lantype_pinyin.userdb/000001.ldb").exists())
        assertArrayEquals(movable, File(files, "rime/personal.dict.yaml").readBytes())
        assertFalse(File(files, "rime/user/personal.dict.yaml").exists())
    }

    @Test fun failedEntryRenameRetainsItsOriginalBytesAndReportsIncomplete() {
        val files = temporaryFolder.newFolder("entry-failure")
        val bytes = byteArrayOf(0, -1, 100)
        val original = write(files, "rime/shared/personal.dict.yaml", bytes)
        val target = File(files, "rime/personal.dict.yaml")
        var calls = 0

        assertFalse(LegacyRimeDirectoryMigration.moveMissingEntries(original.parentFile, target.parentFile) { from, to ->
            calls++
            assertEquals(original, from)
            assertEquals(target, to)
            false
        })
        assertEquals(1, calls)
        assertArrayEquals(bytes, original.readBytes())
        assertFalse(target.exists())
    }

    @Test fun failedWholeDirectoryRenameRetainsEverySourceFile() {
        val files = temporaryFolder.newFolder("directory-failure")
        val bytes = byteArrayOf(-1, -2, 0, 5)
        val original = write(files, "rime/market/personal/words.dict.yaml", bytes)
        val source = File(files, "rime/market")
        val target = File(files, "market")

        assertFalse(LegacyRimeDirectoryMigration.moveMissingEntries(source, target) { from, to ->
            assertEquals(source, from)
            assertEquals(target, to)
            false
        })
        assertArrayEquals(bytes, original.readBytes())
        assertFalse(target.exists())
    }

    @Test fun fullyMovedEntriesAllowOnlyTheEmptyLegacyDirectoryToBeRemoved() {
        val files = temporaryFolder.newFolder("complete")
        val bytes = byteArrayOf(10, 0, -10)
        write(files, "rime/user/personal.dict.yaml", bytes)

        assertTrue(LegacyRimeDirectoryMigration.moveMissingEntries(File(files, "rime/user"), File(files, "rime")))
        assertArrayEquals(bytes, File(files, "rime/personal.dict.yaml").readBytes())
        assertFalse(File(files, "rime/user").exists())
    }

    @Test fun aRestoredLegacyBackupKeepsItsConflictingPersonalDictionaryRecoverable() {
        val files = temporaryFolder.newFolder("restore")
        val current = byteArrayOf(3, 1, -128)
        val restored = byteArrayOf(-1, 4, 0, 8)
        write(files, "rime/lantype_pinyin.userdb/CURRENT", current)
        val archive = ByteArrayOutputStream().also { output ->
            ZipOutputStream(output).use { zip ->
                for ((name, data) in listOf(
                    "_xime_backup/settings.json" to "{}".toByteArray(),
                    "user/lantype_pinyin.userdb/000001.ldb" to restored,
                )) {
                    zip.putNextEntry(ZipEntry(name))
                    zip.write(data)
                    zip.closeEntry()
                }
            }
        }.toByteArray()
        val store = object : BackupPreferenceStore {
            override fun validate(json: ByteArray) { assertEquals("{}", json.toString(Charsets.UTF_8)) }
            override fun snapshot(name: String) = "{}".toByteArray()
            override fun restore(name: String, json: ByteArray, replace: Boolean) {}
        }

        assertTrue(BackupRestoreTransaction.restore(files, store, archive).isSuccess)
        assertFalse(LegacyRimeDirectoryMigration.moveMissingEntries(File(files, "rime/user"), File(files, "rime")))
        assertArrayEquals(restored, File(files, "rime/user/lantype_pinyin.userdb/000001.ldb").readBytes())
        assertArrayEquals(current, File(files, "rime/lantype_pinyin.userdb/CURRENT").readBytes())
    }

    private fun write(root: File, path: String, bytes: ByteArray): File = File(root, path).apply {
        check(parentFile.isDirectory || parentFile.mkdirs())
        writeBytes(bytes)
    }
}
