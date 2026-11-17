#!/usr/bin/env python3
"""Regression tests for the narrow, pinned Gitiles timestamp compatibility path."""
from pathlib import Path
import copy
import importlib.util
import io
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('native_sources', Path(__file__).with_name('restore-native-sources.py'))
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)


class GitilesSourceVerificationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.members = [
            {'path': 'src', 'type': tarfile.DIRTYPE, 'mode': 0o755},
            {'path': 'src/input.cc', 'type': tarfile.REGTYPE, 'mode': 0o644,
             'data': b'int reviewed_source = 1;\n'},
            {'path': 'src/link.cc', 'type': tarfile.SYMTYPE, 'mode': 0o777,
             'linkname': 'input.cc'},
            {'path': 'src/hard.cc', 'type': tarfile.LNKTYPE, 'mode': 0o644,
             'linkname': 'src/input.cc'},
        ]
        self.original = self.write_archive('reviewed.tar.gz', self.members, 1000.125)
        self.entry = {
            'id': 'reviewed-fixture', 'archive_file': 'source.tar.gz',
            'commit': '1' * 40,
            'archive_url': 'https://android.googlesource.com/project/+archive/' + '1' * 40 + '/src.tar.gz',
            'archive_sha256': native.digest(self.original),
            'gitiles_content': native.gitiles_content_identity(self.original),
        }

    def write_archive(self, name, members, mtime=2000.875):
        path = self.root / name
        with tarfile.open(path, mode='w:gz', format=tarfile.PAX_FORMAT) as archive:
            for spec in members:
                item = tarfile.TarInfo(spec['path'])
                item.type, item.mode, item.mtime = spec['type'], spec['mode'], mtime
                for key in ('uid', 'gid', 'uname', 'gname', 'linkname'):
                    if key in spec:
                        setattr(item, key, spec[key])
                item.pax_headers = dict(spec.get('pax', {}))
                data = spec.get('data', b'') if item.isfile() else b''
                item.size = len(data)
                archive.addfile(item, io.BytesIO(data) if item.isfile() else None)
        return path

    def changed(self, mutate):
        members = copy.deepcopy(self.members)
        mutate(members)
        return self.write_archive('changed.tar.gz', members)

    def rejected(self, mutate):
        with self.assertRaises(native.SourceArchiveMismatch):
            native.verify_archive(self.entry, self.changed(mutate))

    def test_reviewed_original_still_uses_archive_sha256(self):
        self.assertEqual('archive-sha256', native.verify_archive(self.entry, self.original)['method'])

    def test_mtime_only_drift_uses_exact_member_identity(self):
        changed = self.changed(lambda members: None)
        self.assertNotEqual(native.digest(self.original), native.digest(changed))
        self.assertEqual(native.GITILES_CONTENT_FORMAT, native.verify_archive(self.entry, changed)['method'])

    def test_same_length_source_byte_change_is_rejected(self):
        self.rejected(lambda members: members[1].update(data=b'int reviewed_source = 2;\n'))

    def test_added_removed_renamed_and_duplicate_paths_are_rejected(self):
        mutations = [
            lambda members: members.append({'path': 'extra.cc', 'type': tarfile.REGTYPE, 'mode': 0o644, 'data': b'x'}),
            lambda members: members.pop(),
            lambda members: members[1].update(path='src/renamed.cc'),
            lambda members: members.append(copy.deepcopy(members[1])),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                self.rejected(mutate)

    def test_type_and_mode_changes_are_rejected(self):
        for values in ({'mode': 0o755}, {'type': tarfile.DIRTYPE}):
            with self.subTest(values=values):
                self.rejected(lambda members: members[1].update(values))

    def test_symlink_and_hardlink_targets_are_rejected(self):
        for index in (2, 3):
            with self.subTest(index=index):
                self.rejected(lambda members: members[index].update(linkname='different.cc'))

    def test_owner_metadata_changes_are_rejected(self):
        for key, value in (('uid', 1), ('gid', 1), ('uname', 'changed'), ('gname', 'changed')):
            with self.subTest(field=key):
                self.rejected(lambda members: members[1].update({key: value}))

    def test_non_mtime_pax_fields_are_rejected(self):
        for key in ('atime', 'comment'):
            with self.subTest(field=key):
                self.rejected(lambda members: members[1].update(pax={key: 'changed'}))

    def test_unpinned_host_commit_or_unapproved_format_cannot_fallback(self):
        drifted = self.changed(lambda members: None)
        changes = [
            {'archive_url': 'https://example.com/+archive/' + '1' * 40 + '.tar.gz'},
            {'commit': '2' * 40},
            {'commit': 'main'},
            {'gitiles_content': {**self.entry['gitiles_content'], 'format': 'unknown'}},
            {'gitiles_content': None},
        ]
        for values in changes:
            with self.subTest(values=values):
                with self.assertRaises(native.SourceArchiveMismatch):
                    native.verify_archive({**self.entry, **values}, drifted)

    def test_other_archive_types_retain_exact_hash_rule(self):
        entry = {**self.entry, 'archive_url': 'https://example.com/source.tar.gz'}
        self.assertEqual('archive-sha256', native.verify_archive(entry, self.original)['method'])
        with self.assertRaises(native.SourceArchiveMismatch):
            native.verify_archive(entry, self.changed(lambda members: None))

    def test_verified_gitiles_cache_needs_no_network(self):
        cache = self.root / 'cache'
        cache.mkdir()
        target = cache / self.entry['archive_file']
        target.write_bytes(self.changed(lambda members: None).read_bytes())
        with patch.object(native.urllib.request, 'urlopen', side_effect=AssertionError('Unexpected network')):
            self.assertEqual(target, native.obtain(self.entry, cache, download=False))

    def test_corrupt_archive_is_rejected(self):
        corrupt = self.root / 'corrupt.tar.gz'
        corrupt.write_bytes(b'not a gzip or tar archive')
        with self.assertRaises(native.SourceArchiveMismatch):
            native.verify_archive(self.entry, corrupt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
