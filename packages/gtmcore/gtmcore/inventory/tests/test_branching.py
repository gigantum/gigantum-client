import tempfile
import pytest
import os

from gtmcore.configuration.utils import call_subprocess
from gtmcore.inventory.branching import (BranchManager, InvalidBranchName, BranchWorkflowViolation,
    BranchException, MergeError)
from gtmcore.files import FileOperations
from gtmcore.fixtures import (mock_config_file, mock_labbook, mock_labbook_lfs_disabled,
                              sample_src_file, helper_create_remote_repo as _MOCK_create_remote_repo,
                              remote_labbook_repo)

# If importing from remote, does new user's branch get created and does it push properly?

TEST_USER = 'test'


class TestBranching(object):

    def test_is_branch_name_valid(self):
        """ Only allow alphanumeric strings with single dash characters not at ends. """

        bad_strings = ['inval!id', '', '-', '---', '-' * 99, 'cats_' * 12, 'no--no', '-no-no-', 'yikes-' * 50 + 'a',
                       'bad!-bad!', 'no_way-*99', '`cat-99', "nope's-branch", 'nope"s-branch','No-Caps-Or-Anything',
                       'NO-CAPS-AT-ALL-99', 'Violà', 'Güten-Tag']
        for b in bad_strings:
            assert not BranchManager.is_branch_name_valid(b)

        good_strings = ['a', 'hello-there', 'yep-yep-yep', '99', 'hello-99-test', '2-33-44-55-66', 'experiment4',
                        'experiment-4', 'über-weird-name-should-this-work-hmm', '你好']
        for g in good_strings:
            assert BranchManager.is_branch_name_valid(g)

    def test_success_init_and_active_branch(self, mock_labbook_lfs_disabled):
        """ All newly-created repos should be on master branch. """

        bm = BranchManager(mock_labbook_lfs_disabled[2], username=TEST_USER)
        assert bm.active_branch == 'master'
        assert bm.workspace_branch == 'master'


    def test_success_create_branch_simple(self, mock_labbook_lfs_disabled):
        """ Test basic creation of a new branch"""
        t = "my-first-feature-branch"
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username=TEST_USER)
        assert bm.active_branch == 'master'
        bm.create_branch(title=t)
        assert bm.active_branch == t
        assert lb.is_repo_clean is True

    def test_fail_create_branch_duplicate_name(self, mock_labbook_lfs_disabled):
        """ Ensure cannot create a new branch with name of existing branch """
        t = "branch-to-be-made-twice"
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username=TEST_USER)
        bm.create_branch(title=t)
        with pytest.raises(InvalidBranchName):
            bm.create_branch(title=t)

    def test_success_create_branch_then_return_to_master(self, mock_labbook_lfs_disabled):
        """ Test process of creating a new branch, then returning to original and then
            being in a clean state. """
        t = 'my-new-example-feature'
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username=TEST_USER)
        assert bm.active_branch == 'master'
        branch_name = bm.create_branch(title=t)
        assert bm.active_branch == branch_name
        assert lb.is_repo_clean

        bm.workon_branch(bm.workspace_branch)
        assert bm.active_branch == 'master'
        assert lb.active_branch == 'master'
        assert lb.is_repo_clean

    def test_success_remove_branch(self, mock_labbook_lfs_disabled):
        """ Test that branches can be removed locally """

        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username=TEST_USER)

        t = 'branch-to-make-and-then-delete'
        branch_name_to_delete = bm.create_branch(title=t)
        assert branch_name_to_delete in bm.branches_local

        bm.workon_branch(bm.workspace_branch)
        bm.remove_branch(branch_name_to_delete)
        assert branch_name_to_delete not in bm.branches_local

    def test_fail_remove_branch_not_exist(self, mock_labbook_lfs_disabled):
        """ Test remove branch does raises exception when deleting nonexisting branch """
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username=TEST_USER)
        with pytest.raises(InvalidBranchName):
            bm.remove_branch('branch-that-does-not-exist')

    def test_fail_remove_branch_on_active_branch(self, mock_labbook_lfs_disabled):
        """ Test remove branch does raises exception when deleting current branch """
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username=TEST_USER)
        with pytest.raises(BranchException):
            bm.remove_branch(bm.active_branch)

    def test_success_merge_from(self, mock_labbook_lfs_disabled):
        """ Test merging with nonconflicting changes. """
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username=TEST_USER)

        t = 'my-new-example-feature'
        feature_branch_name = bm.create_branch(title=t)
        assert bm.active_branch == feature_branch_name

        bm.workon_branch(bm.workspace_branch)
        FileOperations.makedir(lb, 'code/sillyfolder', create_activity_record=True)
        FileOperations.makedir(lb, 'input/newfolder', create_activity_record=True)

        bm.workon_branch(feature_branch_name)
        FileOperations.makedir(lb, 'output/otherdir', create_activity_record=True)
        bm.merge_from(bm.workspace_branch)

        # Assert repo state is as we expect
        assert os.path.isdir(os.path.join(lb.root_dir, 'code/sillyfolder'))
        assert os.path.isdir(os.path.join(lb.root_dir, 'input/newfolder'))
        assert os.path.isdir(os.path.join(lb.root_dir, 'output/otherdir'))
        assert lb.is_repo_clean

        # Return to original branch and check proper state
        bm.workon_branch(bm.workspace_branch)
        assert os.path.isdir(os.path.join(lb.root_dir, 'code/sillyfolder'))
        assert os.path.isdir(os.path.join(lb.root_dir, 'input/newfolder'))
        assert not os.path.isdir(os.path.join(lb.root_dir, 'output/otherdir'))
        assert lb.is_repo_clean

    def test_remove_remote_branch(self, mock_labbook_lfs_disabled):
        lb = mock_labbook_lfs_disabled[2]

        with tempfile.TemporaryDirectory() as tempdir:
            call_subprocess('git init .'.split(), tempdir)
            call_subprocess('touch FILE_A'.split(), tempdir)
            call_subprocess('git add FILE_A'.split(), tempdir)
            call_subprocess('git commit -am "message"'.split(), tempdir)
            call_subprocess('git checkout -b remote-branch'.split(), cwd=tempdir)
            call_subprocess('git checkout master'.split(), cwd=tempdir)
            lb.git.add_remote('origin', tempdir)
            bm = BranchManager(lb, username=TEST_USER)
            bm.fetch()
            assert 'remote-branch' in bm.branches_remote

            # Get this remote branch locally, but go back to master
            bm.workon_branch('remote-branch')
            call_subprocess('git checkout master'.split(), cwd=bm.repository.root_dir)
            bm.remove_remote_branch('remote-branch')

            bm.fetch()

            # Confirm branch exists locally, but is gone on remote.
            assert 'remote-branch' in bm.branches_local
            assert 'remote-branch' not in bm.branches_remote

    def test_merge_conflict_basic(self, mock_labbook_lfs_disabled):
        """ Test a basic merge-conflict scenario with a conflict on one file.
            First, assert that a MergeError is raised when the conflict is detected
            Second, test the force flag to overwrite the conflict using the incoming branch."""
        lb = mock_labbook_lfs_disabled[2]

        # Insert a text file into the master branch of lb
        with open('/tmp/s1.txt', 'w') as s1:
            s1.write('original-file\ndata')
        FileOperations.insert_file(lb, section='code', src_file=s1.name)

        # Create a new branch from this point and make a change to s1.txt
        bm = BranchManager(lb, username=TEST_USER)
        feature_name = bm.create_branch("example-feature-branch")
        with open('/tmp/s1.txt', 'w') as s1:
            s1.write('new-changes-in\nfeature-branch')
        FileOperations.insert_file(lb, section='code', src_file=s1.name)

        # Switch back to the main branch and make a new, conflicting change.
        bm.workon_branch(bm.workspace_branch)
        assert lb.is_repo_clean
        assert not os.path.exists(os.path.join(lb.root_dir, 'output/sample'))
        with open('/tmp/s1.txt', 'w') as s1:
            s1.write('upstream-changes-from-workspace')
        FileOperations.insert_file(lb, section='code', src_file=s1.name, dst_path='')

        # Switch back to feature branch -- make sure that failed merges rollback to state before merge.
        bm.workon_branch(feature_name)
        cp = bm.repository.git.commit_hash
        with pytest.raises(MergeError):
            bm.merge_from(bm.workspace_branch)

        assert lb.is_repo_clean

        # Now try to force merge, and changes are taken from the workspace-branch
        bm.merge_use_ours(bm.workspace_branch)
        assert open(os.path.join(lb.root_dir, 'code', 's1.txt')).read(1000) == \
            'new-changes-in\nfeature-branch'
        assert lb.is_repo_clean

        # Reset this branch
        call_subprocess(f'git reset --hard {cp}'.split(), cwd=bm.repository.root_dir)
        bm.merge_use_theirs(bm.workspace_branch)
        assert open(os.path.join(lb.root_dir, 'code', 's1.txt')).read(1000) == \
               'upstream-changes-from-workspace'
        assert lb.is_repo_clean

    def test_success_rollback_basic(self, mock_labbook_lfs_disabled):
        """ Basic test of rollback feature - making a branch from """
        test_user_lb = mock_labbook_lfs_disabled[2]

        # Create a directory and capture that Git revision (to be used as basis for rollback).
        FileOperations.makedir(test_user_lb, relative_path='code/folder1', create_activity_record=True)
        commit = test_user_lb.git.commit_hash

        # Make follow-up changes to be reverted (sort of).
        FileOperations.makedir(test_user_lb, relative_path='code/folder2', create_activity_record=True)
        FileOperations.makedir(test_user_lb, relative_path='code/folder3', create_activity_record=True)

        # Make rollback branch from Git revision captured above.
        bm = BranchManager(test_user_lb, username=TEST_USER)
        new_b = bm.create_branch('rollback-from-folder-1', revision=commit)
        FileOperations.makedir(test_user_lb, relative_path='input/branch-folder', create_activity_record=True)
        # Check state of repo is as exptected
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'code/folder1'))
        assert not os.path.exists(os.path.join(test_user_lb.root_dir, 'code/folder2'))
        assert not os.path.exists(os.path.join(test_user_lb.root_dir, 'code/folder3'))

        # Now, make chagnes to rollback branch
        FileOperations.makedir(test_user_lb, relative_path='input/branch-1', create_activity_record=True)
        FileOperations.makedir(test_user_lb, relative_path='input/branch-2', create_activity_record=True)
        FileOperations.makedir(test_user_lb, relative_path='input/branch-3', create_activity_record=True)

        # Now, try pulling upstream changes back into the rollback branch, then demonstrate state
        # is as expected.
        bm.merge_from(bm.workspace_branch)
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'code/folder2'))
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'code/folder3'))
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'input/branch-1'))
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'input/branch-2'))
        assert os.path.exists(os.path.join(test_user_lb.root_dir, 'input/branch-3'))
        assert test_user_lb.is_repo_clean

    def test_fail_create_rollback_to_invalid_revision(self, mock_labbook_lfs_disabled):
        """ Fail when provided with an invalid Git revision """
        test_user_lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(test_user_lb, username=TEST_USER)
        with pytest.raises(InvalidBranchName):
            bm.create_branch('should-fail', revision='invalidrevision')

    def test_no_remote_branches_when_no_remote(self, mock_labbook_lfs_disabled):
        test_user_lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(test_user_lb, username=TEST_USER)
        assert bm.branches_remote == []

    def test_assert_all_remote_branches_can_be_checked_out(self,
                                                           remote_labbook_repo,
                                                           mock_labbook_lfs_disabled):
        # Make sure all local branches can be checked out
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username=TEST_USER)

        # There is a remote branch called "testing-branch"
        lb.add_remote("origin", remote_labbook_repo)
        for branch_name in bm.branches_remote:
            bm.workon_branch(branch_name)

    def test_get_commits_with_local_changes(self, mock_config_file, remote_labbook_repo,
                                            mock_labbook_lfs_disabled):
        # When the branch is up to date, ensure it doesn't report being behind.
        lb = mock_labbook_lfs_disabled[2]
        lb.add_remote("origin", remote_labbook_repo)
        bm = BranchManager(lb, username='test')
        bm.workon_branch("testing-branch")

        # Do some stuff to make commits locally
        FileOperations.makedir(lb, 'code/rand_dir', create_activity_record=True)
        FileOperations.delete_files(lb, 'code', ['rand_dir'])

        behind = bm.get_commits_behind()
        ahead = bm.get_commits_ahead()
        assert ahead == 2
        assert behind == 0

    def test_get_commits_with_remote_changes(self, mock_config_file,
                                             remote_labbook_repo,
                                             mock_labbook_lfs_disabled):
        # When the branch is up to date, ensure it doesn't report being behind.
        lb = mock_labbook_lfs_disabled[2]
        lb.add_remote("origin", remote_labbook_repo)
        bm = BranchManager(lb, username='test')
        bm.workon_branch("testing-branch")

        from gtmcore.inventory.inventory import InventoryManager
        remote_lb = InventoryManager().load_labbook_from_directory(remote_labbook_repo)
        remote_bm = BranchManager(remote_lb, 'test')
        remote_bm.workon_branch("testing-branch")
        FileOperations.makedir(remote_lb, 'code/xyzdir', create_activity_record=True)

        bm.fetch()
        behind = bm.get_commits_behind()
        ahead = bm.get_commits_ahead()
        assert ahead == 0
        assert behind == 1

    def test_count_commits_behind_remote_when_no_change(self, mock_config_file, remote_labbook_repo,
                                                        mock_labbook_lfs_disabled):
        # When the branch is up to date, ensure it doesn't report being behind.
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username='test')
        lb.add_remote("origin", remote_labbook_repo)
        bm.workon_branch('testing-branch')

        bm.fetch()
        behind = bm.get_commits_behind()
        ahead = bm.get_commits_ahead()
        assert ahead == 0
        assert behind == 0

    def test_count_commits_behind_for_local_branch(self, mock_config_file, remote_labbook_repo,
                                                   mock_labbook_lfs_disabled):
        # When we're using a local branch, by definition it is never behind.
        lb = mock_labbook_lfs_disabled[2]
        bm = BranchManager(lb, username='test')
        lb.add_remote("origin", remote_labbook_repo)
        bm.create_branch("super-local-branch")

        bm.fetch()
        behind = bm.get_commits_behind()
        ahead = bm.get_commits_ahead()

        # Should be up-to-date.
        assert ahead == 0
        assert behind == 0
