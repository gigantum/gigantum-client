from typing import Optional
import pytest
import mock
import responses
import tempfile
import shutil
import subprocess
import os
from pkg_resources import resource_filename
import time
import glob
from mock import patch
from collections import namedtuple

from gtmcore.configuration.utils import call_subprocess
from gtmcore.gitlib import RepoLocation
from gtmcore.inventory.inventory import InventoryManager, InventoryException
from gtmcore.workflows import GitWorkflowException, LabbookWorkflow, DatasetWorkflow, MergeOverride
from gtmcore.workflows.gitworkflows_utils import create_remote_gitlab_repo
from gtmcore.fixtures import (helper_create_remote_repo as _MOCK_create_remote_repo, mock_labbook_lfs_disabled,
                              mock_config_file)
from gtmcore.inventory.branching import BranchManager, MergeError

from gtmcore.dispatcher import Dispatcher
import gtmcore.dispatcher.dataset_jobs
from gtmcore.dataset.manifest import Manifest
from gtmcore.fixtures.datasets import helper_append_file
from gtmcore.dataset.io.manager import IOManager


def _mock_fetch(self, remote):
    assert isinstance(remote, str)
    pass


class TestGitWorkflowsMethods(object):
    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_publish__simple(self, mock_labbook_lfs_disabled):
        """Test a simple publish and ensuring master is active branch. """
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username)
        bm.create_branch('test-local-only')
        assert bm.branches_remote == []
        assert bm.branches_local == ['master', 'test-local-only']

        wf = LabbookWorkflow(lb)

        # Test you can only publish on master.
        with pytest.raises(GitWorkflowException):
            wf.publish(username=username)
        assert wf.remote is None

        # Once we return to master branch, then we can publish.
        bm.workon_branch(bm.workspace_branch)
        wf.publish(username=username)
        assert os.path.exists(wf.remote)

        # Assert that publish only pushes up the master branch.
        assert bm.branches_local == ['master', 'test-local-only']
        assert bm.branches_remote == ['master']

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_publish__cannot_overwrite(self, mock_labbook_lfs_disabled):
        """ Test cannot publish a project already published. """
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)
        wf.publish(username=username)
        with pytest.raises(GitWorkflowException):
            wf.publish(username=username)

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_publish__publish_then_import_with_another_user(self, mock_labbook_lfs_disabled, mock_config_file):
        """ Test cannot publish a project already published. """
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)
        wf.publish(username=username)

        other_user = 'other-test-user'

        remote = RepoLocation(wf.remote, other_user)
        wf_other = LabbookWorkflow.import_from_remote(remote, username=other_user)
        lb_other = wf_other.repository
        assert lb_other.root_dir != lb.root_dir

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_publish__publish_then_import_then_sync(self, mock_labbook_lfs_disabled, mock_config_file):
        """ Test cannot publish a project already published. """
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)
        wf.publish(username=username)

        other_user = 'other-test-user'
        remote = RepoLocation(wf.remote, other_user)
        wf_other = LabbookWorkflow.import_from_remote(remote, username=other_user)
        with open(os.path.join(wf_other.repository.root_dir, 'testfile'), 'w') as f: f.write('filedata')
        wf_other.repository.sweep_uncommitted_changes()

        wf_other.sync(username=other_user)
        commit_hash = wf_other.repository.git.commit_hash

        assert wf.repository.git.commit_hash != commit_hash
        wf.sync(username=username)
        assert len(wf.repository.git.commit_hash) == len(commit_hash)
        assert wf.repository.git.commit_hash == commit_hash

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_import_from_remote__nominal(self, mock_labbook_lfs_disabled, mock_config_file):
        """ test import_from_remote method """
        username = 'testuser'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)
        wf.publish(username=username)

        other_user = 'other-test-user2'
        remote = RepoLocation(wf.remote, other_user)
        wf_other = LabbookWorkflow.import_from_remote(remote, username=other_user)
        # The remotes must be the same, cause it's the same remote repo
        assert wf_other.remote == remote.remote_location
        # The actual path on disk will be different, though
        assert wf_other.repository != wf.repository
        # Check imported into namespace of original owner (testuser)
        assert f'{other_user}/{username}/labbooks/labbook1' in wf_other.repository.root_dir

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_import_from_remote__dataset(self, mock_labbook_lfs_disabled, mock_config_file):
        """ test importing a published dataset """
        username = 'testuser'
        lb = mock_labbook_lfs_disabled[2]
        im = InventoryManager()
        ds = im.create_dataset(username, username, 'test-ds', storage_type='gigantum_object_v1')

        wf = DatasetWorkflow(ds)
        wf.publish(username=username)

        other_user = 'other-test-user2'
        remote = RepoLocation(wf.remote, other_user)
        wf_other = DatasetWorkflow.import_from_remote(remote, username=other_user)

        # The remotes must be the same, cause it's the same remote repo
        assert wf_other.remote == remote.remote_location
        # The actual path on disk will be different, though
        assert wf_other.repository != wf.repository
        # Check imported into namespace of original owner (testuser)
        assert f'{other_user}/{username}/datasets/test-ds' in wf_other.repository.root_dir

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_import_from_remote__linked_dataset(self, mock_labbook_lfs_disabled, mock_config_file):
        """ test importing a project with a linked dataset"""
        def dispatcher_mock(self, function_ref, kwargs, metadata):
            assert kwargs['logged_in_username'] == 'other-test-user2'
            assert kwargs['dataset_owner'] == 'testuser'
            assert kwargs['dataset_name'] == 'test-ds'

            # Stop patching so job gets scheduled for real
            dispatcher_patch.stop()

            # Call same method as in mutation
            d = Dispatcher()
            res = d.dispatch_task(gtmcore.dispatcher.dataset_jobs.check_and_import_dataset,
                                  kwargs=kwargs, metadata=metadata)

            return res

        username = 'testuser'
        lb = mock_labbook_lfs_disabled[2]
        im = InventoryManager()
        ds = im.create_dataset(username, username, 'test-ds', storage_type='gigantum_object_v1')

        # Publish dataset
        dataset_wf = DatasetWorkflow(ds)
        dataset_wf.publish(username=username)

        # Link to project
        im.link_dataset_to_labbook(dataset_wf.remote, username, username, lb, username)

        # Publish project
        labbook_wf = LabbookWorkflow(lb)
        labbook_wf.publish(username=username)

        # Patch dispatch_task so you can inject the mocked config file
        dispatcher_patch = patch.object(Dispatcher, 'dispatch_task', dispatcher_mock)
        dispatcher_patch.start()

        # Import project, triggering an auto-import of the dataset
        other_user = 'other-test-user2'
        remote = RepoLocation(labbook_wf.remote, other_user)
        wf_other = LabbookWorkflow.import_from_remote(remote, username=other_user)

        # The remotes must be the same, cause it's the same remote repo
        assert wf_other.remote == remote.remote_location
        # The actual path on disk will be different, though
        assert wf_other.repository != labbook_wf.repository
        # Check imported into namespace of original owner (testuser)
        assert f'{other_user}/{username}/labbooks/labbook1' in wf_other.repository.root_dir

        cnt = 0
        while cnt < 20:
            try:
                im_other_user = InventoryManager()
                ds = im_other_user.load_dataset(other_user, username, 'test-ds')
                break
            except InventoryException:
                cnt += 1
                time.sleep(1)

        assert cnt < 20
        assert ds.name == 'test-ds'
        assert ds.namespace == username
        assert mock_config_file[1] in ds.root_dir

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_sync__linked_dataset(self, mock_labbook_lfs_disabled, mock_config_file):
        """ test syncing a project that pulls in a linked dataset"""
        def dispatcher_mock(self, function_ref, kwargs, metadata):
            assert kwargs['logged_in_username'] == 'other-test-user2'
            assert kwargs['dataset_owner'] == 'testuser'
            assert kwargs['dataset_name'] == 'test-ds'

            # Stop patching so job gets scheduled for real
            dispatcher_patch.stop()

            # Call same method as in mutation
            d = Dispatcher()
            res = d.dispatch_task(gtmcore.dispatcher.dataset_jobs.check_and_import_dataset,
                                  kwargs=kwargs, metadata=metadata)

            return res

        username = 'testuser'
        lb = mock_labbook_lfs_disabled[2]
        im = InventoryManager()
        ds = im.create_dataset(username, username, 'test-ds', storage_type='gigantum_object_v1')

        # Publish dataset
        dataset_wf = DatasetWorkflow(ds)
        dataset_wf.publish(username=username)

        # Publish project
        labbook_wf = LabbookWorkflow(lb)
        labbook_wf.publish(username=username)

        # Import project
        other_user = 'other-test-user2'
        remote = RepoLocation(labbook_wf.remote, other_user)
        wf_other = LabbookWorkflow.import_from_remote(remote, username=other_user)

        # The remotes must be the same, cause it's the same remote repo
        assert wf_other.remote == remote.remote_location
        assert wf_other.repository != labbook_wf.repository
        assert f'{other_user}/{username}/labbooks/labbook1' in wf_other.repository.root_dir

        with pytest.raises(InventoryException):
            im_other_user = InventoryManager()
            ds = im_other_user.load_dataset(other_user, username, 'test-ds')

        # Link to project
        im.link_dataset_to_labbook(dataset_wf.remote, username, username, lb, username)

        # Sync project with linked dataset
        labbook_wf.sync(username=username)

        # Patch dispatch_task so you can inject the mocked config file
        dispatcher_patch = patch.object(Dispatcher, 'dispatch_task', dispatcher_mock)
        dispatcher_patch.start()

        # Sync on the other end, get the dataset!
        wf_other.sync(username=other_user)

        cnt = 0
        while cnt < 20:
            try:
                im_other_user = InventoryManager()
                ds = im_other_user.load_dataset(other_user, username, 'test-ds')
                break
            except InventoryException:
                cnt += 1
                time.sleep(1)

        assert cnt < 20
        assert ds.name == 'test-ds'
        assert ds.namespace == username
        assert mock_config_file[1] in ds.root_dir

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_checkout__linked_dataset(self, mock_labbook_lfs_disabled, mock_config_file):
        """ test checking out a branch in a project that pulls in a linked dataset"""
        def dispatcher_mock(self, function_ref, kwargs, metadata):
            assert kwargs['logged_in_username'] == 'other-test-user2'
            assert kwargs['dataset_owner'] == 'testuser'
            assert kwargs['dataset_name'] == 'test-ds'

            # Stop patching so job gets scheduled for real
            dispatcher_patch.stop()

            # Call same method as in mutation
            d = Dispatcher()
            res = d.dispatch_task(gtmcore.dispatcher.dataset_jobs.check_and_import_dataset,
                                  kwargs=kwargs, metadata=metadata)

            return res

        username = 'testuser'
        lb = mock_labbook_lfs_disabled[2]
        im = InventoryManager()
        ds = im.create_dataset(username, username, 'test-ds', storage_type='gigantum_object_v1')

        # Publish dataset
        dataset_wf = DatasetWorkflow(ds)
        dataset_wf.publish(username=username)

        # Publish project
        labbook_wf = LabbookWorkflow(lb)
        labbook_wf.publish(username=username)

        # Switch branches
        labbook_wf.labbook.checkout_branch(branch_name="dataset-branch", new=True)

        # Link to project
        im.link_dataset_to_labbook(dataset_wf.remote, username, username, labbook_wf.labbook, username)

        # Publish branch
        labbook_wf.sync(username=username)

        # Import project
        other_user = 'other-test-user2'
        remote = RepoLocation(labbook_wf.remote, other_user)
        wf_other = LabbookWorkflow.import_from_remote(remote, username=other_user)

        # The remotes must be the same, cause it's the same remote repo
        assert wf_other.remote == remote.remote_location
        assert wf_other.repository != labbook_wf.repository
        assert f'{other_user}/{username}/labbooks/labbook1' in wf_other.repository.root_dir

        with pytest.raises(InventoryException):
            im_other_user = InventoryManager()
            ds = im_other_user.load_dataset(other_user, username, 'test-ds')

        # Patch dispatch_task so you can inject the mocked config file
        dispatcher_patch = patch.object(Dispatcher, 'dispatch_task', dispatcher_mock)
        dispatcher_patch.start()

        # Checkout the branch
        assert wf_other.labbook.active_branch == "master"
        wf_other.checkout(username=other_user, branch_name="dataset-branch")

        cnt = 0
        while cnt < 20:
            try:
                im_other_user = InventoryManager()
                ds = im_other_user.load_dataset(other_user, username, 'test-ds')
                break
            except InventoryException:
                cnt += 1
                time.sleep(1)

        assert cnt < 20
        assert ds.name == 'test-ds'
        assert ds.namespace == username
        assert mock_config_file[1] in ds.root_dir
        assert wf_other.labbook.active_branch == "dataset-branch"

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_sync___simple_push_to_master(self, mock_labbook_lfs_disabled, mock_config_file):
        """ test import_from_remote method """
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)
        wf.publish(username=username)
        fpath = os.path.join(lb.root_dir, 'input', 'testfile')
        with open(fpath, 'w') as f: f.write('filedata')
        lb.sweep_uncommitted_changes()
        wf.sync(username=username)

        # Check hash on remote - make sure it matches local.
        remote_hash = call_subprocess('git log -n 1 --oneline'.split(), cwd=wf.remote).split()[0]
        assert remote_hash in lb.git.commit_hash

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_sync___push_up_new_branch(self, mock_labbook_lfs_disabled, mock_config_file):
        """ test import_from_remote method """
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)
        wf.publish(username=username)
        bm = BranchManager(lb, username='test')
        bm.create_branch('new-branch-to-push')
        assert 'new-branch-to-push' not in bm.branches_remote
        wf.sync('test')
        assert 'new-branch-to-push' in bm.branches_remote

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_sync___push_up_then_sync(self, mock_labbook_lfs_disabled, mock_config_file):
        """ test import_from_remote method """
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)
        wf.publish(username=username)
        bm = BranchManager(lb, username='test')
        bm.create_branch('new-branch-to-push')
        wf.sync('test')

        # Make some change locally and commit, then sync.
        fpath = os.path.join(lb.root_dir, 'input', 'testfile')
        with open(fpath, 'w') as f: f.write('filedata')
        lb.sweep_uncommitted_changes()
        wf.sync(username=username)

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_sync___detect_merge_conflict(self, mock_labbook_lfs_disabled, mock_config_file):
        """ test import_from_remote method """
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)
        wf.publish(username=username)
        bm = BranchManager(lb, username='test')
        bm.create_branch('test-conflict-branch')
        fpath1 = os.path.join(lb.root_dir, 'input', 'testfile1')
        with open(fpath1, 'w') as f:
            f.write('filedata1')
        fpath2 = os.path.join(lb.root_dir, 'input', 'testfile2')
        with open(fpath2, 'w') as f:
            f.write('filedata2')
        lb.sweep_uncommitted_changes()
        wf.sync('test')

        other_user = 'other-test-user2'
        remote = RepoLocation(wf.remote, other_user)
        wf_other = LabbookWorkflow.import_from_remote(remote, username=other_user)
        bm_other = BranchManager(wf_other.labbook, username=other_user)
        bm_other.workon_branch('test-conflict-branch')
        with open(os.path.join(wf_other.labbook.root_dir, 'input', 'testfile1'), 'w') as f:
            f.write('conflicting-change-other-user1')
        with open(os.path.join(wf_other.labbook.root_dir, 'input', 'testfile2'), 'w') as f:
            f.write('conflicting-change-other-user2')
        wf_other.labbook.sweep_uncommitted_changes()
        wf_other.sync(username=username)

        with open(fpath1, 'w') as f:
            f.write('conflicting-change-original-user')
        with open(fpath2, 'w') as f:
            f.write('conflicting-change-original-user')
        wf.labbook.sweep_uncommitted_changes()
        h = wf.labbook.git.commit_hash
        with pytest.raises(MergeError):
            n = wf.sync(username=username)
        assert h == wf.labbook.git.commit_hash

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_sync___override_merge_conflict_theirs(self, mock_labbook_lfs_disabled, mock_config_file):
        """ test sync, with override in case of merge conflict. """
        """ test import_from_remote method """
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)
        wf.publish(username=username)
        bm = BranchManager(lb, username='test')
        bm.create_branch('test-conflict-branch')
        fpath = os.path.join(lb.root_dir, 'input', 'testfile')
        with open(fpath, 'w') as f: f.write('filedata')
        lb.sweep_uncommitted_changes()
        wf.sync('test')

        other_user = 'other-test-user2'
        remote = RepoLocation(wf.remote, other_user)
        wf_other = LabbookWorkflow.import_from_remote(remote, username=other_user)
        bm_other = BranchManager(wf_other.labbook, username=other_user)
        bm_other.workon_branch('test-conflict-branch')
        with open(os.path.join(wf_other.labbook.root_dir, 'input', 'testfile'), 'w') as f:
            f.write('conflicting-change-other-user')
        wf_other.labbook.sweep_uncommitted_changes()
        wf_other.sync(username=username)

        assert wf_other.repository.root_dir != wf.repository.root_dir
        fpath = os.path.join(wf.labbook.root_dir, 'input', 'testfile')
        with open(fpath, 'w') as f: f.write('conflicting-change-original-user')
        wf.labbook.sweep_uncommitted_changes()
        assert wf.labbook.is_repo_clean
        h = wf.labbook.git.commit_hash

        n = wf.sync(username=username, override=MergeOverride.THEIRS)
        assert h != wf.labbook.git.commit_hash
        flines = open(os.path.join(wf.labbook.root_dir, 'input', 'testfile')).read()
        assert 'conflicting-change-other-user' == flines

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_sync___override_merge_conflict_ours(self, mock_labbook_lfs_disabled, mock_config_file):
        """ test sync, with override in case of merge conflict. """
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)
        wf.publish(username=username)
        bm = BranchManager(lb, username='test')
        bm.create_branch('test-conflict-branch')
        fpath = os.path.join(lb.root_dir, 'input', 'testfile')
        with open(fpath, 'w') as f: f.write('filedata')
        lb.sweep_uncommitted_changes()
        wf.sync('test')

        other_user = 'other-test-user2'
        remote = RepoLocation(wf.remote, other_user)
        wf_other = LabbookWorkflow.import_from_remote(remote, username=other_user)
        bm_other = BranchManager(wf_other.labbook, username=other_user)
        bm_other.workon_branch('test-conflict-branch')
        with open(os.path.join(wf_other.labbook.root_dir, 'input', 'testfile'), 'w') as f:
            f.write('conflicting-change-other-user')
        wf_other.labbook.sweep_uncommitted_changes()
        wf_other.sync(username=username)

        fpath = os.path.join(wf.labbook.root_dir, 'input', 'testfile')
        with open(fpath, 'w') as f: f.write('conflicting-change-original-user')
        wf.labbook.sweep_uncommitted_changes()
        n = wf.sync(username=username, override=MergeOverride.OURS)
        flines = open(os.path.join(wf.labbook.root_dir, 'input', 'testfile')).read()
        assert 'conflicting-change-original-user' == flines

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_reset__no_op(self, mock_labbook_lfs_disabled, mock_config_file):
        """ test reset performs no operation when there's nothing to do """
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)
        wf.reset(username=username)
        wf.publish(username=username)

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_reset__reset_local_change_same_owner(self, mock_labbook_lfs_disabled):
        """ test reset performs no operation when there's nothing to do """
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)
        wf.publish(username=username)
        commit_to_check = lb.git.commit_hash

        # Make some change locally and commit
        fpath = os.path.join(lb.root_dir, 'input', 'testfile')
        with open(fpath, 'w') as f:
            f.write('filedata')
        lb.sweep_uncommitted_changes()
        assert lb.git.commit_hash != commit_to_check

        # Make an UNTRACKED change locally, make sure it gets clared up
        untracked_file = os.path.join(lb.root_dir, 'output', 'untracked-file')
        with open(untracked_file, 'w') as f:
            f.write('untracked data')

        # Do a reset and make sure state resets appropriately
        wf.reset(username=username)
        assert lb.git.commit_hash == commit_to_check
        assert not os.path.exists(fpath)
        assert not os.path.exists(untracked_file)
        remote_hash = call_subprocess('git log -n 1 --oneline'.split(), cwd=wf.remote).split()[0]
        assert remote_hash in lb.git.commit_hash

    def test_migrate_old_schema_1_project(self, mock_config_file):
        """ Test migrating a very old schema 1/gm.workspace LabBook """
        p = resource_filename('gtmcore', 'workflows')
        p2 = os.path.join(p, 'tests', 'snappy.zip')

        with tempfile.TemporaryDirectory() as td:
            call_subprocess(f"unzip {p2} -d {td}".split(), cwd=td)
            temp_lb_path = os.path.join(td, 'snappy')

            # Tests backwards compatibility (test.zip is a very old schema 1 LabBook)
            lb = InventoryManager().load_labbook_from_directory(temp_lb_path)
            wf = LabbookWorkflow(lb)

            wf.labbook.remove_remote()
            wf.migrate()

            # Test that current branch is as appropriate
            assert wf.labbook.active_branch == 'master'

            # Test that there is an activity record indicate migration
            assert any(['Migrate schema to 2' in c['message'] for c in wf.labbook.git.log()[:5]])

            # Test schema has successfully rolled to 2
            assert wf.labbook.schema == 2

            # Test that untracked space exists (if we add something to untracked space)
            assert wf.labbook.is_repo_clean
            with open(os.path.join(lb.root_dir, 'output/untracked', 'untracked-file'), 'wb') as fb:
                fb.write(b'cat' * 100)
            assert wf.labbook.is_repo_clean

    def test_migrate_no_op_on_new_labbook(self, mock_labbook_lfs_disabled):
        username = 'test'
        lb = mock_labbook_lfs_disabled[2]
        wf = LabbookWorkflow(lb)

        h1 = wf.labbook.git.commit_hash
        wf.migrate()

        # No change of git status after no-op migration
        assert h1 == wf.labbook.git.commit_hash

    def test_should_migrate_on_old_project(self, mock_config_file):
        p = resource_filename('gtmcore', 'workflows')
        p2 = os.path.join(p, 'tests', 'lb-to-migrate-197b6a.zip')
        with tempfile.TemporaryDirectory() as tempdir:
            lbp = shutil.copyfile(p2, os.path.join(tempdir, 'lb-to-migrate.zip'))
            subprocess.run(f'unzip lb-to-migrate.zip'.split(),
                           check=True, cwd=tempdir)

            im = InventoryManager()
            lb = im.load_labbook_from_directory(os.path.join(tempdir, 'lb-to-migrate'))
            wf = LabbookWorkflow(lb)

            assert wf.should_migrate() is True

            wf.migrate()

            assert wf.labbook.active_branch == 'master'
            assert wf.should_migrate() is False

            wf.labbook.git.checkout('gm.workspace')
            assert wf.should_migrate() is False

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_publish__dataset(self, mock_config_file):
        def update_feedback(msg: str, has_failures: Optional[bool] = None, failure_detail: Optional[str] = None,
                            percent_complete: Optional[float] = None):
            """Method to update the job's metadata and provide feedback to the UI"""
            assert has_failures is None or has_failures is False
            assert failure_detail is None

        def dispatch_query_mock(self, job_key):
            JobStatus = namedtuple("JobStatus", ['status', 'meta'])
            return JobStatus(status='finished', meta={'completed_bytes': '500'})

        def dispatch_mock(self, method_reference, kwargs, metadata, persist):
                return "afakejobkey"

        username = 'test'
        im = InventoryManager()
        ds = im.create_dataset(username, username, 'dataset-1', 'gigantum_object_v1')
        m = Manifest(ds, username)
        wf = DatasetWorkflow(ds)

        # Put a file into the dataset that needs to be pushed
        helper_append_file(m.cache_mgr.cache_root, m.dataset_revision, "test1.txt", "asdfadfsdf")
        m.sweep_all_changes()

        iom = IOManager(ds, m)
        assert len(glob.glob(f'{iom.push_dir}/*')) == 1

        with patch.object(Dispatcher, 'dispatch_task', dispatch_mock):
            with patch.object(Dispatcher, 'query_task', dispatch_query_mock):
                wf.publish(username=username, feedback_callback=update_feedback)
                assert os.path.exists(wf.remote)
                assert len(glob.glob(f'{iom.push_dir}/*')) == 0

    @mock.patch('gtmcore.workflows.gitworkflows_utils.create_remote_gitlab_repo', new=_MOCK_create_remote_repo)
    def test_sync__dataset(self, mock_config_file):
        def update_feedback(msg: str, has_failures: Optional[bool] = None, failure_detail: Optional[str] = None,
                            percent_complete: Optional[float] = None):
            """Method to update the job's metadata and provide feedback to the UI"""
            assert has_failures is None or has_failures is False
            assert failure_detail is None

        def dispatch_query_mock(self, job_key):
            JobStatus = namedtuple("JobStatus", ['status', 'meta'])
            return JobStatus(status='finished', meta={'completed_bytes': '100'})

        def dispatch_mock(self, method_reference, kwargs, metadata, persist):
                return "afakejobkey"

        username = 'test'
        im = InventoryManager()
        ds = im.create_dataset(username, username, 'dataset-1', 'gigantum_object_v1')
        m = Manifest(ds, username)
        wf = DatasetWorkflow(ds)

        iom = IOManager(ds, m)
        assert len(glob.glob(f'{iom.push_dir}/*')) == 0
        wf.publish(username=username, feedback_callback=update_feedback)

        # Put a file into the dataset that needs to be pushed
        helper_append_file(m.cache_mgr.cache_root, m.dataset_revision, "test1.txt", "asdfadfsdf")
        m.sweep_all_changes()

        assert len(glob.glob(f'{iom.push_dir}/*')) == 1
        with patch.object(Dispatcher, 'dispatch_task', dispatch_mock):
            with patch.object(Dispatcher, 'query_task', dispatch_query_mock):
                wf.sync(username=username, feedback_callback=update_feedback)
                assert os.path.exists(wf.remote)
                assert len(glob.glob(f'{iom.push_dir}/*')) == 0

    @responses.activate
    @mock.patch('gtmcore.gitlib.git_fs_shim.GitFilesystemShimmed.fetch', new=_mock_fetch)
    def test_create_remote_gitlab_repo(self, mock_config_file):
        responses.add(responses.POST, 'https://test.gigantum.com/api/v1/',
                      json={'data': {'additionalCredentials': {'gitServiceToken': 'afaketoken'}}}, status=200)

        responses.add(responses.GET, 'https://test.repo.gigantum.com/api/v4/projects/test%2Flabbook-1',
                      status=404)
        responses.add(responses.POST, 'https://test.repo.gigantum.com/api/v4/projects', status=201)

        username = 'test'
        im = InventoryManager()
        lb = im.create_labbook(username, username, 'labbook-1')

        with pytest.raises(ValueError):
            create_remote_gitlab_repo(lb, username, 'private', 'afakeaccesstoken', None)

        create_remote_gitlab_repo(lb, username, 'private', 'afakeaccesstoken', "afakeidtoken")

        assert lb.remote == 'https://test@test.repo.gigantum.com/test/labbook-1.git/'

