import pytest
import os
from collections import OrderedDict
import time
import redis
import glob

from gtmcore.dataset import Manifest
from gtmcore.inventory.inventory import InventoryManager

from gtmcore.fixtures.datasets import mock_dataset_with_cache_dir, mock_dataset_with_manifest, helper_append_file, \
    USERNAME, mock_legacy_dataset, mock_config_class, mock_enable_unmanaged_for_testing


class TestManifest(object):
    def test_init(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        assert isinstance(manifest.manifest, OrderedDict)
        assert manifest.dataset_revision == ds.git.repo.head.commit.hexsha

    def test_get_num_hashing_cpus(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        assert manifest.get_num_hashing_cpus() > 1

    def test_status_created_files(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test_dir"))
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir"))
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test_dir", "nested"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "dfg")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test_dir/test3.txt",
                           "asdffdgfghghfjjgh")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test_dir/nested/test4.txt",
                           "565656565")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test5.txt",
                           "dfasdfhfgjhg")

        status = manifest.status()
        assert len(status.created) == 8
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        assert "test1.txt" in status.created
        assert "test2.txt" in status.created
        assert "test_dir/test3.txt" in status.created
        assert "test_dir/nested/test4.txt" in status.created
        assert "other_dir/test5.txt" in status.created
        assert "test_dir/" in status.created
        assert "test_dir/nested/" in status.created
        assert "other_dir/" in status.created

    def test_update_simple(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdf")

        status = manifest.status()
        assert len(status.created) == 1
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        assert "test1.txt" in status.created

        manifest.update(status=status)
        time.sleep(2)

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdf")

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 1
        assert len(status.deleted) == 0

        manifest.update()

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

    def test_update_simple_with_reloading(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdf")

        status = manifest.status()
        assert len(status.created) == 1
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        assert "test1.txt" in status.created

        manifest.update(status=status)
        time.sleep(2)

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        m2 = Manifest(mock_dataset_with_manifest[0], 'tester')

        helper_append_file(m2.cache_mgr.cache_root, m2.dataset_revision, "test1.txt", "asdfasdf")

        status = m2.status()
        assert len(status.created) == 0
        assert len(status.modified) == 1
        assert len(status.deleted) == 0

        m2.update()

        status = m2.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

    def test_status_deleted_files(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "54455445")

        status = manifest.status()
        assert len(status.created) == 2
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        assert "test1.txt" in status.created
        assert "test2.txt" in status.created

        manifest.update(status=status)

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        os.remove(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt"))

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 1

        manifest.update()

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        assert 'test1.txt' not in manifest.manifest

        # Reload a new manifest instance and verify no file
        m2 = Manifest(mock_dataset_with_manifest[0], 'tester')
        assert 'test1.txt' not in m2.manifest
        assert 'test2.txt' in m2.manifest

    def test_update_complex(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test_dir"))
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir"))
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test_dir", "nested"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "dfg")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test_dir/test3.txt",
                           "asdffdgfghghfjjgh")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test_dir/nested/test4.txt",
                           "565656565")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test5.txt",
                           "dfasdfhfgjhg")

        status = manifest.status()
        assert len(status.created) == 8
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        assert "test1.txt" in status.created
        assert "test2.txt" in status.created
        assert "test_dir/test3.txt" in status.created
        assert "test_dir/nested/test4.txt" in status.created
        assert "other_dir/test5.txt" in status.created
        assert "test_dir/" in status.created
        assert "test_dir/nested/" in status.created
        assert "other_dir/" in status.created

        manifest.update()

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test99.txt", "ghghgh")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "dfghghgfg")
        os.remove(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test_dir", "nested",
                               "test4.txt"))

        status = manifest.status()
        assert len(status.created) == 1
        assert len(status.modified) == 1
        assert len(status.deleted) == 1
        assert "test99.txt" in status.created
        assert "test2.txt" in status.modified
        assert "test_dir/nested/test4.txt" in status.deleted

        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "test_dir", "nested", "test4.txt")) is False
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "test99.txt")) is True

        manifest.update()

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

    def test_list(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test3.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test4.txt",
                           "dfasdfhfgjhg")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test5.txt",
                           "fdghdfgsa")
        manifest.update()

        file_info, indexes = manifest.list()
        assert len(file_info) == 6
        assert indexes == list(range(0, 6))
        assert file_info[3]['key'] == "test1.txt"
        assert file_info[3]['size'] == '8'
        assert file_info[3]['is_local'] is True
        assert file_info[3]['is_dir'] is False
        assert 'modified_at' in file_info[3]
        assert file_info[0]['key'] == "other_dir/"
        assert file_info[0]['size'] == '0'
        assert file_info[0]['is_local'] is True
        assert file_info[0]['is_dir'] is True
        assert 'modified_at' in file_info[0]
        assert file_info[1]['key'] == "other_dir/test4.txt"
        assert file_info[2]['key'] == "other_dir/test5.txt"
        assert file_info[4]['key'] == "test2.txt"
        assert file_info[5]['key'] == "test3.txt"

        file_info, indexes = manifest.list(first=1)
        assert indexes == list(range(0, 1))
        assert len(file_info) == 1
        assert file_info[0]['key'] == "other_dir/"

        file_info, indexes = manifest.list(first=2)
        assert indexes == list(range(0, 2))
        assert len(file_info) == 2
        assert file_info[0]['key'] == "other_dir/"
        assert file_info[1]['key'] == "other_dir/test4.txt"

        file_info, indexes = manifest.list(first=3, after_index=1)
        assert indexes == list(range(2, 5))
        assert len(file_info) == 3
        assert file_info[0]['key'] == "other_dir/test5.txt"
        assert file_info[1]['key'] == "test1.txt"
        assert file_info[2]['key'] == "test2.txt"

        file_info, indexes = manifest.list(first=300, after_index=2)
        assert len(file_info) == 3
        assert indexes == list(range(3, 6))
        assert file_info[0]['key'] == "test1.txt"
        assert file_info[1]['key'] == "test2.txt"
        assert file_info[2]['key'] == "test3.txt"

        os.remove(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt"))
        file_info, indexes = manifest.list()
        assert indexes == list(range(0, 6))
        assert len(file_info) == 6
        assert file_info[3]['key'] == "test1.txt"
        assert file_info[3]['size'] == '8'
        assert file_info[3]['is_local'] is False
        assert file_info[3]['is_dir'] is False

    def test_get(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test4.txt",
                           "dfasdfhfgjhg")
        manifest.update()

        file_info = manifest.get("test1.txt")
        assert file_info['key'] == "test1.txt"
        assert file_info['size'] == '8'
        assert file_info['is_local'] is True
        assert file_info['is_dir'] is False
        assert 'modified_at' in file_info

        file_info = manifest.get("other_dir/test4.txt")
        assert file_info['key'] == "other_dir/test4.txt"

    def test_file_info_from_filesystem(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test4.txt",
                           "dfasdfhfgjhg")

        file_info = manifest.gen_file_info("test1.txt")
        assert file_info['key'] == "test1.txt"
        assert file_info['size'] == '8'
        assert file_info['is_local'] is True
        assert file_info['is_dir'] is False
        assert 'modified_at' in file_info

        file_info = manifest.gen_file_info("other_dir/")
        assert file_info['key'] == "other_dir/"
        assert file_info['size'] == '0'
        assert file_info['is_local'] is True
        assert file_info['is_dir'] is True
        assert 'modified_at' in file_info

    def test_sweep_all_changes(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "asdfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test3.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test4.txt",
                           "dfasdfhfgjhg")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test5.txt",
                           "fdghdfgsa")

        assert len(ds.git.log()) == 4

        status = manifest.status()
        assert len(status.created) == 6
        assert len(status.modified) == 0
        assert len(status.deleted) == 0
        print(manifest.manifest.keys())
        manifest.sweep_all_changes()
        print(manifest.manifest.keys())
        time.sleep(2)
        status = manifest.status()
        print(manifest.manifest.keys())
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfafdfdfdfdsdf")
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 1
        assert len(status.deleted) == 0
        manifest.sweep_all_changes()
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        os.remove(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt"))
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 1
        manifest.sweep_all_changes()
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        num_records = len(ds.git.log())

        # Should run again, doing nothing and creation 0 new activity records
        manifest.sweep_all_changes()
        assert num_records == len(ds.git.log())

        assert len(manifest.manifest.keys()) == 5
        assert 'other_dir/' in manifest.manifest
        assert 'other_dir/test4.txt' in manifest.manifest
        assert 'other_dir/test5.txt' in manifest.manifest
        assert 'test2.txt' in manifest.manifest
        assert 'test3.txt' in manifest.manifest

    def test_sweep_all_changes_directory(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir1"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir1/test1.txt", "asdfasdfdf")
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir5"))
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir2"))
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir2", "dir3"))
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir2", "dir3", "dir4"))

        assert len(ds.git.log()) == 4

        status = manifest.status()
        assert len(status.created) == 6
        assert len(status.modified) == 0
        assert len(status.deleted) == 0
        manifest.sweep_all_changes()
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        assert len(manifest.manifest.keys()) == 6
        assert 'dir1/' in manifest.manifest
        assert 'dir1/test1.txt' in manifest.manifest
        assert 'dir2/' in manifest.manifest
        assert 'dir5/' in manifest.manifest
        assert 'dir2/dir3/' in manifest.manifest
        assert 'dir2/dir3/dir4/' in manifest.manifest

        src = os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir1")
        dest = os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir1-renamed")
        os.rename(src, dest)

        status = manifest.status()
        assert len(status.created) == 2
        assert len(status.modified) == 0
        assert len(status.deleted) == 2
        manifest.sweep_all_changes()
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        src = os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir5")
        dest = os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir5-renamed")
        os.rename(src, dest)
        status = manifest.status()
        assert len(status.created) == 1
        assert len(status.modified) == 0
        assert len(status.deleted) == 1
        manifest.sweep_all_changes()
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

    def test_sweep_all_changes_remove_file_in_dir(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir1"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir1/test1.txt", "asdfasdfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "dfdf")

        assert len(ds.git.log()) == 4

        status = manifest.status()
        assert len(status.created) == 3
        assert len(status.modified) == 0
        assert len(status.deleted) == 0
        manifest.sweep_all_changes()
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        assert len(manifest.manifest.keys()) == 3
        assert 'dir1/' in manifest.manifest
        assert 'dir1/test1.txt' in manifest.manifest
        assert 'test2.txt' in manifest.manifest

        src = os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "dir1", "test1.txt")
        os.remove(src)
        time.sleep(1.5)

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 1
        assert 'dir1/test1.txt' in status.deleted

        manifest.sweep_all_changes()
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        assert len(manifest.manifest.keys()) == 2
        assert 'dir1/' in manifest.manifest
        assert 'test2.txt' in manifest.manifest

    @pytest.mark.skip("Currently writing to files when dups exists causes issues with status due to links")
    def test_sweep_all_changes_with_dup_files(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test3.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test4.txt",
                           "dfasdfhfgjhg")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test5.txt",
                           "fdghdfgsa")

        assert len(ds.git.log()) == 4

        status = manifest.status()
        assert len(status.created) == 5
        assert len(status.modified) == 0
        assert len(status.deleted) == 0
        manifest.sweep_all_changes()
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdf")
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 1
        assert len(status.deleted) == 0
        manifest.sweep_all_changes()
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

    def test_delete(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "asdfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test3.txt", "asdfasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test4.txt",
                           "dfasdfhfgjhg")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test5.txt",
                           "fdghdfgsa")
        manifest.sweep_all_changes()

        num_records = len(ds.git.log())
        assert num_records == 6

        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "test1.txt")) is True
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "test2.txt")) is True
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "test3.txt")) is True
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "other_dir", "test4.txt")) is True
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "other_dir", "test5.txt")) is True

        manifest.delete(["test1.txt"])
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "test1.txt")) is False
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "test2.txt")) is True
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "test3.txt")) is True
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "other_dir", "test4.txt")) is True
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "other_dir", "test5.txt")) is True
        assert len(ds.git.log()) == num_records + 2

        manifest.delete(["test2.txt", "other_dir/"])
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "test1.txt")) is False
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "test2.txt")) is False
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "test3.txt")) is True
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "other_dir", "test4.txt")) is False
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                                           "other_dir", "test5.txt")) is False
        assert len(ds.git.log()) == num_records + 4

    def test_move_rename_file(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir"))
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir", "nested_dir"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdghndfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "asdfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                           "other_dir/nested_dir/test6.txt", "4456tyfg")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision,
                           "other_dir/nested_dir/test7.txt", "fgfyytr")
        manifest.sweep_all_changes()

        num_records = len(ds.git.log())
        assert num_records == 6

        revision = manifest.dataset_revision
        cr = manifest.cache_mgr.cache_root
        assert os.path.exists(os.path.join(cr, revision, "test1.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "test2.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test6.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test7.txt")) is True

        # test renaming a file
        edges = manifest.move("test1.txt", "test1-moved.txt")
        assert len(edges) == 1
        assert edges[0]['key'] == 'test1-moved.txt'
        assert edges[0]['size'] == '14'
        assert edges[0]['is_local'] is True

        revision = manifest.dataset_revision
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root,
                                           manifest.dataset_revision, "test1.txt")) is False
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root,
                                           manifest.dataset_revision, "test1-moved.txt")) is True
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root,
                                           manifest.dataset_revision, "test2.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test6.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test7.txt")) is True
        assert len(ds.git.log()) == num_records + 2

    def test_move_rename_dir(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir"))
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir", "nested_dir"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdghndfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "asdfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/nested_dir/test6.txt", "4456tyfg")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/nested_dir/test7.txt", "fgfyytr")
        manifest.sweep_all_changes()

        num_records = len(ds.git.log())
        assert num_records == 6

        revision = manifest.dataset_revision
        cr = manifest.cache_mgr.cache_root
        assert os.path.exists(os.path.join(cr, revision, "test1.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "test2.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test6.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test7.txt")) is True

        # Test renaming a directory
        edges = manifest.move("other_dir/", "new_dir/")
        assert len(edges) == 4
        assert edges[0]['key'] == 'new_dir/'
        assert edges[1]['key'] == 'new_dir/nested_dir/'
        assert edges[2]['key'] == 'new_dir/nested_dir/test6.txt'
        assert edges[3]['key'] == 'new_dir/nested_dir/test7.txt'

        revision = manifest.dataset_revision
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt")) is True
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test6.txt")) is False
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test7.txt")) is False
        assert os.path.exists(os.path.join(cr, revision, "new_dir", "nested_dir", "test6.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "new_dir", "nested_dir", "test7.txt")) is True
        assert len(ds.git.log()) == num_records + 2

    def test_move_move_dir_up(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir"))
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir", "nested_dir"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdghndfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "asdfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/test3.txt", "4456tyfg")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/nested_dir/test6.txt", "4456tyfg")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/nested_dir/test7.txt", "fgfyytr")
        manifest.sweep_all_changes()

        num_records = len(ds.git.log())
        assert num_records == 6

        revision = manifest.dataset_revision
        cr = manifest.cache_mgr.cache_root
        assert os.path.exists(os.path.join(cr, revision, "test1.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "test2.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "test3.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test6.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test7.txt")) is True

        # Test moving a directory up a level
        edges = manifest.move("other_dir/nested_dir/", "moved_nested_dir/")
        assert len(edges) == 3
        assert edges[0]['key'] == 'moved_nested_dir/'
        assert edges[1]['key'] == 'moved_nested_dir/test6.txt'
        assert edges[2]['key'] == 'moved_nested_dir/test7.txt'

        revision = manifest.dataset_revision
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt")) is True
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "test3.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test6.txt")) is False
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test7.txt")) is False
        assert os.path.exists(os.path.join(cr, revision, "moved_nested_dir", "test6.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "moved_nested_dir", "test7.txt")) is True
        assert len(ds.git.log()) == num_records + 2

    def test_move_move_dir_in(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "first_dir"))
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir"))
        os.makedirs(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir", "nested_dir"))
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdghndfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "asdfdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "first_dir/test3.txt", "4456tyfg")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/nested_dir/test6.txt", "4456tyfg")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "other_dir/nested_dir/test7.txt", "fgfyytr")
        manifest.sweep_all_changes()

        num_records = len(ds.git.log())
        assert num_records == 6

        revision = manifest.dataset_revision
        cr = manifest.cache_mgr.cache_root
        assert os.path.exists(os.path.join(cr, revision, "test1.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "test2.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "first_dir", "test3.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test6.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test7.txt")) is True

        edges = manifest.move("first_dir/", "other_dir/nested_dir/")
        assert len(edges) == 2
        assert edges[0]['key'] == 'other_dir/nested_dir/first_dir'
        assert edges[1]['key'] == 'other_dir/nested_dir/first_dir/test3.txt'

        revision = manifest.dataset_revision
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root,
                                           manifest.dataset_revision, "test1.txt")) is True
        assert os.path.exists(os.path.join(manifest.cache_mgr.cache_root,
                                           manifest.dataset_revision, "test2.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir")) is True
        assert os.path.exists(os.path.join(cr, revision, "first_dir", "test3.txt")) is False
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "first_dir", "test3.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test6.txt")) is True
        assert os.path.exists(os.path.join(cr, revision, "other_dir", "nested_dir", "test7.txt")) is True
        assert len(ds.git.log()) == num_records + 2

    def test_create_directory(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        assert len(ds.git.log()) == 4
        assert len(manifest.manifest) == 0

        previous_revision_dir = manifest.cache_mgr.current_revision_dir
        assert os.path.isdir(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, 'test1')) is False

        manifest.create_directory("test1/")

        assert len(ds.git.log()) == 6
        assert len(manifest.manifest) == 1
        assert 'test1/' in manifest.manifest
        assert previous_revision_dir != manifest.cache_mgr.current_revision_dir
        assert os.path.isdir(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, 'test1')) is True

        assert "Created new empty directory `test1/`" in ds.git.log()[0]['message']

        manifest.create_directory("test1/test2/")

        assert len(ds.git.log()) == 8
        assert len(manifest.manifest) == 2
        assert 'test1/' in manifest.manifest
        assert 'test1/test2/' in manifest.manifest
        assert previous_revision_dir != manifest.cache_mgr.current_revision_dir
        assert os.path.isdir(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, 'test1')) is True
        assert os.path.isdir(os.path.join(manifest.cache_mgr.cache_root,
                                          manifest.dataset_revision, 'test1', 'test2')) is True

        assert "Created new empty directory `test1/test2/`" in ds.git.log()[0]['message' ]

    def test_create_directory_errors(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest

        with pytest.raises(ValueError):
            manifest.create_directory("test1/test2/")

        manifest.create_directory("test1/")
        with pytest.raises(ValueError):
            manifest.create_directory("test1/")

    def test_legacy_manifest(self, mock_legacy_dataset):
        ds, manifest, working_dir = mock_legacy_dataset
        assert len(manifest.manifest) == 3
        assert 'IdeaPF.pdf' in manifest.manifest
        assert 'test_folder/gitflow.vdx' in manifest.manifest

        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asddfdffasdf")

        status = manifest.status()
        assert len(status.created) == 1
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        assert "test1.txt" in status.created

        manifest.update(status=status)
        time.sleep(2)

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        m2 = Manifest(ds, 'tester')

        helper_append_file(m2.cache_mgr.cache_root, m2.dataset_revision, "test1.txt", "asdfasdf")

        status = m2.status()
        assert len(status.created) == 0
        assert len(status.modified) == 1
        assert len(status.deleted) == 0

        m2.update()

        status = m2.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        assert len(m2.manifest) == 4
        assert 'IdeaPF.pdf' in m2.manifest
        assert 'test_folder/gitflow.vdx' in m2.manifest

    def test_update_and_delete_from_legacy_manifest(self, mock_legacy_dataset):
        ds, manifest, working_dir = mock_legacy_dataset
        assert len(manifest.manifest) == 3
        assert 'IdeaPF.pdf' in manifest.manifest
        assert 'test_folder/gitflow.vdx' in manifest.manifest

        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asddfdffasdf")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "IdeaPF.pdf", "fake data")

        status = manifest.status()
        assert len(status.created) == 1
        assert len(status.modified) == 1
        assert len(status.deleted) == 0
        assert len(manifest.manifest) == 3
        manifest.update(status=status)

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0
        assert len(manifest.manifest) == 4

        os.remove(os.path.join(manifest.cache_mgr.cache_root, manifest.dataset_revision, 'IdeaPF.pdf'))

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 1

        manifest.update()

        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0
        assert len(manifest.manifest) == 3

        assert 'IdeaPF.pdf' not in manifest.manifest

        # Test reloading (should be from cache)
        m2 = Manifest(ds, 'tester')
        assert len(m2.manifest) == 3
        assert 'IdeaPF.pdf' not in m2.manifest
        assert 'test_folder/gitflow.vdx' in m2.manifest
        assert 'test1.txt' in m2.manifest

        # Test reloading (should be from files)
        client = redis.StrictRedis(db=1)
        client.delete(m2._manifest_io.manifest_cache_key)

        m3 = Manifest(ds, 'tester')
        assert len(m3.manifest) == 3
        assert 'IdeaPF.pdf' not in m3.manifest
        assert 'test_folder/gitflow.vdx' in m3.manifest
        assert 'test1.txt' in m3.manifest

    def test_multiple_contexts(self, mock_dataset_with_manifest):
        ds, manifest, working_dir = mock_dataset_with_manifest
        checkout_context_file = os.path.join(ds.root_dir, '.gigantum', '.checkout')
        im = InventoryManager()

        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test1.txt", "asdfasdf")
        manifest.update()
        status = manifest.status()
        assert len(status.created) == 0
        assert len(status.modified) == 0
        assert len(status.deleted) == 0

        assert len(manifest.manifest) == 1

        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test2.txt", "2212121")
        manifest.update()
        assert len(manifest.manifest) == 2
        os.remove(checkout_context_file)

        # Load new context
        ds = im.load_dataset(USERNAME, USERNAME, ds.name)
        manifest = Manifest(ds, USERNAME)

        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test3.txt", "454")
        manifest.update()
        assert len(manifest.manifest) == 3
        assert manifest.manifest['test3.txt']['b'] == '3'
        os.remove(checkout_context_file)

        # Load new context
        ds = im.load_dataset(USERNAME, USERNAME, ds.name)
        manifest = Manifest(ds, USERNAME)

        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test4.txt", "fgfgfdfd")
        helper_append_file(manifest.cache_mgr.cache_root, manifest.dataset_revision, "test3.txt", "dfdfddfdfdfdfd")
        manifest.update()
        assert len(manifest.manifest) == 4
        assert manifest.manifest['test3.txt']['b'] == '17'

        # Test reloading (should be from cache)

        # Load new context
        ds = im.load_dataset(USERNAME, USERNAME, ds.name)
        manifest = Manifest(ds, USERNAME)
        assert len(manifest.manifest) == 4
        assert 'test1.txt' in manifest.manifest
        assert 'test2.txt' in manifest.manifest
        assert 'test3.txt' in manifest.manifest
        assert 'test4.txt' in manifest.manifest
        assert manifest.manifest['test3.txt']['b'] == '17'

        # Test reloading (should be from files)
        client = redis.StrictRedis(db=1)
        client.delete(manifest._manifest_io.manifest_cache_key)

        ds = im.load_dataset(USERNAME, USERNAME, ds.name)
        manifest = Manifest(ds, USERNAME)
        assert len(manifest.manifest) == 4
        assert 'test1.txt' in manifest.manifest
        assert 'test2.txt' in manifest.manifest
        assert 'test3.txt' in manifest.manifest
        assert 'test4.txt' in manifest.manifest
        assert manifest.manifest['test3.txt']['b'] == '17'

        assert len(glob.glob(os.path.join(ds.root_dir, 'manifest', 'manifest-*'))) == 3

    def test_evict(self, mock_config_class):
        im, conf_file, working_dir = mock_config_class
        ds = im.create_dataset(USERNAME, USERNAME, 'dataset-1', description="my dataset 1",
                               storage_type="local_filesystem")
        m = Manifest(ds, USERNAME)

        helper_append_file(m.cache_mgr.cache_root, m.dataset_revision, "test1.txt", "asdfasdf")
        helper_append_file(m.cache_mgr.cache_root, m.dataset_revision, "test2.txt", "asdfasdf")
        m.sweep_all_changes()

        assert len(m.manifest) == 2
        file_info = m.get("test1.txt")
        assert file_info['key'] == "test1.txt"
        file_info = m.get("test2.txt")
        assert file_info['key'] == "test2.txt"

        # Remove checkout context so a new manifest file gets made
        checkout_file = os.path.join(ds.root_dir, '.gigantum', '.checkout')
        os.remove(checkout_file)

        # Reload classes
        ds = im.load_dataset(USERNAME, USERNAME, 'dataset-1')
        m = Manifest(ds, USERNAME)

        # Add file and verify
        helper_append_file(m.cache_mgr.cache_root, m.dataset_revision, "test3.txt", "new content")
        m.sweep_all_changes()

        assert len(m.manifest) == 3
        file_info = m.get("test1.txt")
        assert file_info['key'] == "test1.txt"
        file_info = m.get("test2.txt")
        assert file_info['key'] == "test2.txt"
        file_info = m.get("test3.txt")
        assert file_info['key'] == "test3.txt"

        # Remove NEW manifest file
        _, checkout_id = ds.checkout_id.rsplit('-', 1)
        manifest_file = f'manifest-{checkout_id}.json'
        os.remove(os.path.join(ds.root_dir, 'manifest', manifest_file))

        # Reload classes
        ds = im.load_dataset(USERNAME, USERNAME, 'dataset-1')
        m = Manifest(ds, USERNAME)

        # Verify manifest hasn't changed
        assert len(m.manifest) == 3
        file_info = m.get("test1.txt")
        assert file_info['key'] == "test1.txt"
        file_info = m.get("test2.txt")
        assert file_info['key'] == "test2.txt"
        file_info = m.get("test3.txt")
        assert file_info['key'] == "test3.txt"

        # Evict from cache
        m.force_reload()

        # Verify manifest HAS changed
        assert len(m.manifest) == 2
        file_info = m.get("test1.txt")
        assert file_info['key'] == "test1.txt"
        file_info = m.get("test2.txt")
        assert file_info['key'] == "test2.txt"
