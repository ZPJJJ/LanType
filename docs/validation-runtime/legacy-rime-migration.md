# Legacy Rime directory migration: data-preservation fix

Review baseline: `60903e8`. The defect concerns conflicting or unmoved legacy files, not an ordinary upgrade of the current flat directory layout.

## Trigger and observed loss

The current application uses `files/rime/` for both Rime user and shared data. Personal LevelDB databases are direct children named `<dictionary>.userdb/`; the packaged full-pinyin schema declares `dictionary: pinyin_simp`, and the existing backup tests include the legacy `rime_ice.userdb/` name. Imported packages are stored under `files/market/`. Normal 1.1.0 use does not create the former `rime/user/`, `rime/shared/`, or `rime/market/` layout.

The recovery path still accepts legacy Rime-relative archive entries. `BackupRestoreTransaction.restore` places a non-metadata entry such as `user/rime_ice.userdb/000001.ldb` under `files/rime/user/rime_ice.userdb/`. `BackupManager.importBackup` then requests redeployment. `RimeConfigHelper.initializeRimeDataAsync` runs the legacy directory migrations before preparing current resources.

Before the fix, migration skipped an entry when its flat destination already existed, ignored a failed `renameTo`, and finally called `deleteRecursively` on the old directory. Thus an accepted legacy archive could lose its restored personal dictionary when the application already had a database with the same name. The old market-directory merge had the same deletion behavior.

This was reproduced with temporary directories, fixture bytes, the unchanged production backup-restoration transaction, and the original migration method bodies extracted from the source. The three-case probe asserted:

1. A legacy backup was accepted and its personal database file existed after restoration; migration then deleted the old database directory because the flat database already existed. The current flat database remained unchanged.
2. Without a destination conflict, the legacy database moved successfully and its personal-file bytes were preserved.
3. A legacy market package with the same name as an existing package was deleted without transferring its personal dictionary.

The structured result, source hashes, exact host harness, and adaptation limits are in `legacy-rime-migration-before.json`. This is a filesystem reproduction, not an Android or valid-LevelDB runtime test.

## Minimal change

`LegacyRimeDirectoryMigration.moveMissingEntries` replaces the destructive cleanup in both migration paths. It moves an entire directory when the destination is absent. When the destination exists, it moves only missing top-level entries. It never recursively merges database files or overwrites an existing entry. Finally, `File.delete()` removes the source directory only if it is empty.

A conflicting entry or failed move therefore remains at its original path, such as `files/rime/user/rime_ice.userdb/`, `files/rime/shared/personal.dict.yaml`, or `files/rime/market/custom/`. The caller logs a partial migration through the existing logger. The already active flat resource remains active.

**Retaining conflicting data makes it recoverable; it does not automatically merge or enable it.** Database reconciliation and a user-facing conflict-resolution workflow are outside this change.

## Regression evidence

All seven methods in `LegacyRimeDirectoryMigrationTest` passed in an independent JVM run using Kotlin compiler 2.3.20 and JUnit 4.13.2. The run compiled the actual new helper, actual test source, and unchanged production `BackupRestoreTransaction`. Only the unrelated Android-facing `BackupManager` constants/allowlist object was replaced by the same small fixture stub used in the reproduction. The result was `OK (7 tests)`.

The seven cases cover:

- An existing flat layout with no legacy directories stays byte-for-byte unchanged.
- A whole legacy market directory moves into an absent destination with unchanged bytes.
- Conflicting files and whole databases retain both source and destination bytes; nonconflicting entries still move.
- An entry-level rename failure retains the original bytes and reports incomplete migration.
- A whole-directory rename failure retains its source and does not create a false destination.
- Successfully moved entries allow the empty old directory to be removed.
- An accepted legacy backup followed by the new migration retains its conflicting personal database file for recovery.

Rename-failure cases inject a failed filesystem-operation result; they do not simulate a particular Android storage fault. The source and target assertions use real temporary files.

All seven cases then passed in the 2026-11-17 serial Android Gradle batch, using the actual application source and backup code without the independent host probe's stub. The class had zero failures, errors or skips; its raw XML is preserved at `../validation-1.1.1/junit/final/TEST-com.kingzcheung.xime.rime.LegacyRimeDirectoryMigrationTest.xml`. The full first serial batch's two failures belong to clipboard-test timestamp preconditions, not migration; all first-run XML remains under `../validation-1.1.1/junit/first-serial/`.

These are filesystem and Android Gradle test results, not native input-engine or device acceptance. `git diff --check` passed after the changes.
