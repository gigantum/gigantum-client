import pytest
import os
import time
from pathlib import Path
from hashlib import blake2b

from gtmcore.dataset.manifest.hash import SmartHash
from gtmcore.fixtures.datasets import mock_dataset_with_cache_dir, mock_dataset_with_manifest


def helper_append_file(cache_dir, revision, rel_path, content):
    with open(os.path.join(cache_dir, revision, rel_path), 'at') as fh:
        fh.write(content)


class TestHashing(object):
    def test_init(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        sh = SmartHash(ds.root_dir, manifest.cache_mgr.cache_root, manifest.dataset_revision)

        assert sh.fast_hash_data == {}

    @pytest.mark.asyncio
    async def test_hash(self, event_loop, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        sh = SmartHash(ds.root_dir, manifest.cache_mgr.cache_root, manifest.dataset_revision)
        cache_dir = manifest.cache_mgr.cache_root
        revision = manifest.dataset_revision

        assert sh.fast_hash_data == {}
        filename = "test1.txt"
        helper_append_file(cache_dir, revision, filename, "pupper")
        assert sh.fast_hash_data == {}
        assert sh.is_cached(filename) is False
        assert os.path.exists(os.path.join(cache_dir, revision, ".smarthash")) is False

        hash_result = await sh.hash([filename])
        hash_result = hash_result[0]
        assert len(hash_result) == 128

    @pytest.mark.asyncio
    async def test_hash_same_as_nonchunked(self, event_loop, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        sh = SmartHash(ds.root_dir, manifest.cache_mgr.cache_root, manifest.dataset_revision)
        cache_dir = manifest.cache_mgr.cache_root
        revision = manifest.dataset_revision

        filename = "test1.txt"
        helper_append_file(cache_dir, revision, filename, "asdfdsfgkdfshuhwedfgft345wfd" * 100000)
        assert sh.fast_hash_data == {}
        assert sh.is_cached(filename) is False
        assert os.path.exists(os.path.join(cache_dir, revision, ".smarthash")) is False

        hash_result = await sh.hash([filename])
        hash_result = hash_result[0]
        h = blake2b()
        with open(sh.get_abs_path(filename), 'rb') as fh:
            h.update(fh.read())

        assert hash_result == h.hexdigest()

    @pytest.mark.asyncio
    async def test_hash_same_as_nonchunked_multiple(self, event_loop, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        sh = SmartHash(ds.root_dir, manifest.cache_mgr.cache_root, manifest.dataset_revision)
        cache_dir = manifest.cache_mgr.cache_root
        revision = manifest.dataset_revision

        filename1 = "test1.txt"
        helper_append_file(cache_dir, revision, filename1, "asdfdsfgkdfshuhwedfgft345wfd" * 100000)
        assert sh.is_cached(filename1) is False

        filename2 = "test2.txt"
        helper_append_file(cache_dir, revision, filename2, "gfggfgfgfgwee" * 100000)
        assert sh.is_cached(filename2) is False
        assert os.path.exists(os.path.join(cache_dir, revision, ".smarthash")) is False
        assert sh.fast_hash_data == {}

        h = blake2b()
        with open(sh.get_abs_path(filename1), 'rb') as fh:
            h.update(fh.read())
        hash1 = h.hexdigest()

        h = blake2b()
        with open(sh.get_abs_path(filename2), 'rb') as fh:
            h.update(fh.read())

        hash2 = h.hexdigest()

        hash_result = await sh.hash([filename1, filename2])
        assert hash1 == hash_result[0]
        assert hash2 == hash_result[1]

        hash_result = await sh.hash([filename2, filename1])
        assert hash2 == hash_result[0]
        assert hash1 == hash_result[1]

    @pytest.mark.asyncio
    async def test_hash_list(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        sh = SmartHash(ds.root_dir, manifest.cache_mgr.cache_root, manifest.dataset_revision)
        cache_dir = manifest.cache_mgr.cache_root
        revision = manifest.dataset_revision

        os.makedirs(os.path.join(cache_dir, revision, "test_dir"))

        filenames = ["test1.txt", "test2.txt", "test3.txt", "test_dir/nested.txt"]
        for f in filenames:
            helper_append_file(cache_dir, revision, f, "sdfadfgfdgh")
        filenames.append('test_dir/')  # Append the directory, since dirs can be stored in the manifest

        hash_results = await sh.hash(filenames)
        assert len(hash_results) == 5

    @pytest.mark.asyncio
    async def test_hash_big(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        sh = SmartHash(ds.root_dir, manifest.cache_mgr.cache_root, manifest.dataset_revision)
        cache_dir = manifest.cache_mgr.cache_root
        revision = manifest.dataset_revision

        os.makedirs(os.path.join(cache_dir, revision, "test_dir"))

        helper_append_file(cache_dir, revision, 'test1.txt', "asdf " * 100000000)
        helper_append_file(cache_dir, revision, 'test2.txt', "hgfd " * 100000000)
        helper_append_file(cache_dir, revision, 'test3.txt', "jjhf " * 10000000)
        helper_append_file(cache_dir, revision, 'test4.txt', "jjhf " * 10000000)

        filenames = ['test1.txt', 'test2.txt', 'test3.txt', 'test4.txt']
        hash_results = await sh.hash(filenames)
        assert len(hash_results) == 4
        for hr in hash_results:
            assert len(hr) == 128

        assert hash_results[0] != hash_results[1]
        assert hash_results[0] != hash_results[2]
        assert hash_results[0] != hash_results[3]
        assert hash_results[1] != hash_results[2]
        assert hash_results[1] != hash_results[3]
        assert hash_results[2] == hash_results[3]

    def test_fast_hash_save(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        sh = SmartHash(ds.root_dir, manifest.cache_mgr.cache_root, manifest.dataset_revision)
        cache_dir = manifest.cache_mgr.cache_root
        revision = manifest.dataset_revision

        assert sh.fast_hash_data == {}
        assert os.path.exists(os.path.join(cache_dir, revision, ".smarthash")) is False
        filename = "test1.txt"
        helper_append_file(cache_dir, revision, filename, "pupper")

        hash_result1 = sh.fast_hash([filename], save=False)
        assert sh.fast_hash_data == {}
        assert os.path.exists(os.path.join(cache_dir, revision, ".smarthash")) is False
        hash_result2 = sh.fast_hash([filename])

        assert hash_result1 == hash_result2
        assert filename in sh.fast_hash_data
        assert os.path.exists(os.path.join(cache_dir, revision, ".smarthash")) is True

    def test_has_changed_fast(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        sh = SmartHash(ds.root_dir, manifest.cache_mgr.cache_root, manifest.dataset_revision)
        cache_dir = manifest.cache_mgr.cache_root
        revision = manifest.dataset_revision

        assert sh.fast_hash_data == {}
        assert os.path.exists(os.path.join(cache_dir, revision, ".smarthash")) is False
        filename = "test1.txt"
        helper_append_file(cache_dir, revision, filename, "pupper")

        assert sh.is_cached(filename) is False

        hash_result = sh.fast_hash([filename])
        hash_result = hash_result[0]
        fname, fsize, mtime = hash_result.split("||")
        assert fname == "test1.txt"
        assert fsize == '6'
        assert sh.fast_hash_data is not None
        assert os.path.exists(os.path.join(cache_dir, revision, ".smarthash")) is True
        assert sh.is_cached(filename) is True

        assert sh.has_changed_fast(filename) is False
        time.sleep(1.1)
        assert sh.has_changed_fast(filename) is False

        # Change file
        helper_append_file(cache_dir, revision, filename, "jgfdjfdgsjfdgsj")
        assert sh.has_changed_fast(filename) is True
        assert sh.has_changed_fast(filename) is True

        sh.fast_hash([filename])
        assert sh.has_changed_fast(filename) is False

        # Touch file, so only change mtime
        time.sleep(1.1)
        Path(sh.get_abs_path(filename)).touch()
        assert sh.has_changed_fast(filename) is True

        sh.fast_hash([filename])
        assert sh.has_changed_fast(filename) is False

    def test_has_changed_fast_from_loaded(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        sh = SmartHash(ds.root_dir, manifest.cache_mgr.cache_root, manifest.dataset_revision)
        cache_dir = manifest.cache_mgr.cache_root
        revision = manifest.dataset_revision

        assert sh.fast_hash_data == {}
        filename = "test1.txt"
        helper_append_file(cache_dir, revision, filename, "pupper")

        hash_result = sh.fast_hash([filename])
        hash_result = hash_result[0]
        fname, fsize, mtime = hash_result.split("||")
        assert fname == "test1.txt"
        assert fsize == '6'
        assert sh.fast_hash_data is not None
        assert os.path.exists(os.path.join(cache_dir, revision, ".smarthash")) is True
        assert sh.is_cached(filename) is True
        assert sh.has_changed_fast(filename) is False

        sh2 = SmartHash(ds.root_dir, cache_dir, revision)
        assert sh2.fast_hash_data is not None
        assert sh2.is_cached(filename) is True
        assert sh2.has_changed_fast(filename) is False
        assert sh2.fast_hash_data[filename] == hash_result

    def test_fast_hash_list(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        sh = SmartHash(ds.root_dir, manifest.cache_mgr.cache_root, manifest.dataset_revision)
        cache_dir = manifest.cache_mgr.cache_root
        revision = manifest.dataset_revision

        os.makedirs(os.path.join(cache_dir, revision, "test_dir"))

        filenames = ["test1.txt", "test2.txt", "test3.txt", "test_dir/nested.txt"]
        for f in filenames:
            helper_append_file(cache_dir, revision, f, "sdfadfgfdgh")
        filenames.append('test_dir/')  # Append the directory, since dirs can be stored in the manifest

        hash_results = sh.fast_hash(filenames)
        assert len(hash_results) == 5

        for fname, result in zip(filenames, hash_results):
            if fname == 'test_dir/':
                assert len(result.split("||")) == 3
                path, fsize, _ = result.split("||")
                assert path == fname
                assert fsize == '0'
            else:
                assert len(result.split("||")) == 3
                path, fsize, _ = result.split("||")
                assert path == fname
                assert fsize == '11'

    def test_fast_hash_big(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        sh = SmartHash(ds.root_dir, manifest.cache_mgr.cache_root, manifest.dataset_revision)
        cache_dir = manifest.cache_mgr.cache_root
        revision = manifest.dataset_revision

        helper_append_file(cache_dir, revision, 'test1.txt', "asdf " * 100000000)
        helper_append_file(cache_dir, revision, 'test2.txt', "hgfd " * 100000000)
        helper_append_file(cache_dir, revision, 'test3.txt', "jjh " * 10000000)
        helper_append_file(cache_dir, revision, 'test4.txt', "jjh " * 10000000)

        filenames = ['test1.txt', 'test2.txt', 'test3.txt', 'test4.txt']
        hash_results = sh.fast_hash(filenames)
        fname, fsize, mtime = hash_results[0].split("||")
        assert 'test1.txt' == fname
        assert fsize == "500000000"

        fname, fsize, mtime = hash_results[1].split("||")
        assert 'test2.txt' in fname
        assert fsize == "500000000"

        fname, fsize, mtime = hash_results[2].split("||")
        assert 'test3.txt' in fname
        assert fsize == "40000000"

        fname, fsize, mtime = hash_results[3].split("||")
        assert 'test4.txt' in fname
        assert fsize == "40000000"

        assert hash_results[2] != hash_results[3]

    def test_get_deleted_files(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        sh = SmartHash(ds.root_dir, manifest.cache_mgr.cache_root, manifest.dataset_revision)
        cache_dir = manifest.cache_mgr.cache_root
        revision = manifest.dataset_revision

        os.makedirs(os.path.join(cache_dir, revision, "test_dir"))

        filenames = ["test1.txt", "test2.txt", "test3.txt", "test_dir/nested.txt"]
        for f in filenames:
            helper_append_file(cache_dir, revision, f, "sdfadfgfdgh")

        hash_results = sh.fast_hash(filenames)
        assert len(hash_results) == 4

        assert len(sh.get_deleted_files(filenames)) == 0

        test_new_filenames = ["test1.txt", "test_dir/nested.txt"]

        deleted = sh.get_deleted_files(test_new_filenames)

        assert len(deleted) == 2
        assert deleted[0] == "test2.txt"
        assert deleted[1] == "test3.txt"
