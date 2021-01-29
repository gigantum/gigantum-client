import pytest
import tempfile
import os
import pprint

from gtmcore.labbook import LabBook
from gtmcore.files import FileOperations as FO
from gtmcore.fixtures import mock_config_file, mock_labbook, remote_labbook_repo, sample_src_file


class TestLabbookFileOperations(object):
    def test_labbook_content_size_simply(self, mock_labbook):
        x, y, lb = mock_labbook

        lb_size = FO.content_size(lb)
        # Make sure the new LB is about 10-35kB. This is about reasonable for a new, emtpy LB.
        assert lb_size > 10000
        assert lb_size < 35000

    def test_insert_file_success_1(self, mock_labbook, sample_src_file):
        lb = mock_labbook[2]
        new_file_data = FO.insert_file(lb, "code", sample_src_file)
        base_name = os.path.basename(sample_src_file)
        assert os.path.exists(os.path.join(lb.root_dir, 'code', base_name))
        assert new_file_data['key'] == f'{base_name}'
        assert new_file_data['is_dir'] is False

    def test_insert_file_upload_id(self, mock_labbook):
        lb = mock_labbook[2]
        test_file = os.path.join(tempfile.gettempdir(), "asdfasdf-testfile.txt")
        with open(test_file, 'wt') as sample_f:
            # Fill sample file with some deterministic crap
            sample_f.write("n4%nm4%M435A EF87kn*C" * 40)

        # This is basically checking for rename
        new_file_data = FO.insert_file(lb, "code", test_file, "testfile.txt")

        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'testfile.txt'))
        assert new_file_data['key'] == 'testfile.txt'
        assert new_file_data['is_dir'] is False

    def test_insert_file_success_2(self, mock_labbook, sample_src_file):
        lb = mock_labbook[2]
        FO.makedir(lb, "output/testdir")
        new_file_data = FO.insert_file(lb, "output", sample_src_file, "testdir")
        base_name = os.path.basename(new_file_data['key'])
        assert os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir', base_name))
        assert new_file_data['key'] == f'testdir/{base_name}'
        assert new_file_data['is_dir'] is False

    def test_insert_and_make_intermediary_directories(self, mock_labbook, sample_src_file):
        lb = mock_labbook[2]
        FO.insert_file(lb, "code", sample_src_file, "/super/random/dir/inside.file")
        p = os.path.join(lb.root_dir, 'code', "super/random/dir/inside.file")
        assert os.path.isfile(p)

    def test_insert_file_fail_due_to_gitignore(self, mock_labbook):
        lb = mock_labbook[2]
        git_hash_1 = lb.git.commit_hash
        lines = [l.strip() for l in open(os.path.join(lb.root_dir, '.gitignore')).readlines()]
        assert any(['.DS_Store' in l for l in lines])

        # Note: .DS_Store is in the gitignore directory.
        test_file = os.path.join(tempfile.gettempdir(), ".DS_Store")
        with open(test_file, 'wt') as sample_f:
            # Fill sample file with some deterministic crap
            sample_f.write("This file should not be allowed to be inserted into labbook. " * 40)

        git_hash_2 = lb.git.commit_hash
        with pytest.raises(Exception):
            r = lb.insert_file('input', src_file=sample_f.name)

        # Make sure no commits were made
        assert git_hash_1 == git_hash_2
        # Make sure the inserted file that doesn't match wasn't added.
        assert '.DS_Store' not in os.listdir(os.path.join(lb.root_dir, 'input'))

    def test_remove_file_success(self, mock_labbook, sample_src_file):
        lb = mock_labbook[2]
        new_file_data = FO.insert_file(lb, "code", sample_src_file)
        base_name = os.path.basename(new_file_data['key'])
        assert os.path.exists(os.path.join(lb.root_dir, 'code', base_name))
        FO.delete_files(lb, 'code', [base_name])
        assert not os.path.exists(os.path.join(lb.root_dir, 'code', base_name))

    def test_remove_file_fail(self, mock_labbook, sample_src_file):
        lb = mock_labbook[2]
        FO.insert_file(lb, "code", sample_src_file)
        new_file_path = os.path.join('blah', 'invalid.txt')
        with pytest.raises(ValueError):
            FO.delete_files(lb, 'code', [new_file_path])

    def test_remove_file_fail_old_prototype(self, mock_labbook, sample_src_file):
        lb = mock_labbook[2]
        new_file_data = FO.insert_file(lb, "code", sample_src_file)
        base_name = os.path.basename(new_file_data['key'])

        assert os.path.exists(os.path.join(lb.root_dir, 'code', base_name))

        with pytest.raises(ValueError):
            FO.delete_files(lb, 'code', base_name)

    def test_remove_dir(self, mock_labbook, sample_src_file):
        lb = mock_labbook[2]
        FO.makedir(lb, "output/testdir")
        new_file_path = FO.insert_file(lb, "output", sample_src_file, "testdir")
        base_name = os.path.basename(new_file_path['key'])

        assert os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir', base_name))
        # Note! Now that remove() uses force=True, no special action is needed for directories.
        # Delete the directory
        FO.delete_files(lb, "output", ["testdir"])
        assert not os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir', base_name))
        assert not os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir'))

    def test_remove_empty_dir(self, mock_labbook, sample_src_file):
        lb = mock_labbook[2]
        FO.makedir(lb, "output/testdir")
        new_file_path = FO.insert_file(lb, "output", sample_src_file, "testdir")
        base_name = os.path.basename(new_file_path['key'])

        assert os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir', base_name))

        # Delete the directory
        FO.delete_files(lb, "output", ["testdir"])
        assert not os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir', base_name))
        assert not os.path.exists(os.path.join(lb.root_dir, 'output', 'testdir'))

    def test_remove_many_files(self, mock_labbook, sample_src_file):
        lb = mock_labbook[2]

        test_files = [f"testfile{x}.txt" for x in range(15)]
        for test_file in test_files:
            with open(os.path.join(lb.root_dir, 'code', test_file), 'wt') as sample_f:
                sample_f.write("blah")

            assert os.path.exists(os.path.join(lb.root_dir, 'code', test_file))
        lb.git.add_all()
        lb.git.commit("making test data")

        FO.delete_files(lb, "code", test_files)

        for test_file in test_files:
            assert not os.path.exists(os.path.join(lb.root_dir, 'code', test_file))

    def test_untracked_file_operations(selfself, mock_labbook):
        lb = mock_labbook[2]
        for base in ['output', 'input', 'code']:
            full_untracked_path = os.path.join(lb.root_dir, base, 'untracked/new-untracked/untracked.txt')

            FO.makedir(lb, f'{base}/untracked/new-untracked')
            with open(full_untracked_path, 'w') as untracked_file:
                untracked_file.write('This is not tracked\n')
            assert os.path.exists(full_untracked_path)

            FO.delete_files(lb, base, ['untracked/new-untracked'])
            assert not os.path.exists(full_untracked_path)

    def test_move_file_as_rename_in_same_dir(self, mock_labbook, sample_src_file):
        lb = mock_labbook[2]
        # insert file
        new_file_data = FO.insert_file(lb, "code", sample_src_file, '')
        base_name = os.path.basename(new_file_data['key'])
        assert os.path.exists(os.path.join(lb.root_dir, 'code', base_name))
        assert new_file_data['key'] == base_name

        # move to rename
        moved_rel_path = os.path.join(f'{base_name}.MOVED')
        r = FO.move_file(lb, 'code', new_file_data['key'], moved_rel_path)
        assert len(r) == 1
        assert not os.path.exists(os.path.join(lb.root_dir, 'code', base_name))
        assert os.path.exists(os.path.join(lb.root_dir, 'code', f'{base_name}.MOVED'))
        assert os.path.isfile(os.path.join(lb.root_dir, 'code', f'{base_name}.MOVED'))

    def test_move_single_file(self, mock_labbook, mock_config_file, sample_src_file):
        lb = mock_labbook[2]
        f = FO.insert_file(lb, 'code', sample_src_file)['key']
        FO.makedir(lb, 'code/target_dir')
        results = FO.move_file(lb, 'code', f, 'target_dir')
        assert len(results) == 1
        pprint.pprint(results)
        assert results[0]['is_dir'] == False
        assert results[0]['key'] == 'target_dir/' + os.path.basename(sample_src_file)

    def test_move_single_file_to_section_top(self, mock_labbook, mock_config_file, sample_src_file):
        lb = mock_labbook[2]
        FO.makedir(lb, 'code/inner_dir')
        f = FO.insert_file(lb, 'code', sample_src_file, 'inner_dir')['key']
        # Move file to top of code section
        results = FO.move_file(lb, 'code', f, dst_rel_path='')

        # Results should be returned for "code" -- the file just moved there and the
        assert len(results) == 1
        assert results[0]['is_dir'] == False
        assert results[0]['key'] == os.path.basename(f)

    def test_move_empty_directory(self, mock_labbook, mock_config_file, sample_src_file):
        lb = mock_labbook[2]

        FO.makedir(lb, 'code/stable_dir')
        FO.makedir(lb, 'code/empty_dir')

        # We'll move "empty_dir" into "stable_dir" - there should only be one element in returned list
        res = FO.move_file(lb, 'code', 'empty_dir', 'stable_dir')
        assert len(res) == 1
        assert res[0]['is_dir'] is True
        assert res[0]['key'] == 'stable_dir/empty_dir/'

    def test_move_loaded_directory_with_one_file(self, mock_labbook, mock_config_file, sample_src_file):
        lb = mock_labbook[2]
        new_file_data = FO.insert_file(lb, "code", sample_src_file)
        base_name = os.path.basename(new_file_data['key'])
        assert os.path.exists(os.path.join(lb.root_dir, 'code', base_name))

        # make new subdir
        os.makedirs(os.path.join(lb.root_dir, 'code', 'subdir'))
        # .. and then put a file in it
        mv_file_res = FO.move_file(lb, "code", base_name, os.path.join('subdir', base_name))
        # Should be 2, because it returns the info of the directory it was moved into
        assert len(mv_file_res) == 1
        assert mv_file_res[0]['key'] == f'subdir/{base_name}'
        assert mv_file_res[0]['is_dir'] == False

        # Move "subdir" into "target_dir", there should be two activity records
        FO.makedir(lb, "code/target_dir", create_activity_record=True)
        mv_dir_res = FO.move_file(lb, "code", 'subdir', 'target_dir')
        assert len(mv_dir_res) == 2
        assert mv_dir_res[0]['key'] == 'target_dir/subdir/'
        assert mv_dir_res[0]['is_dir'] is True
        assert mv_dir_res[1]['key'] == f'target_dir/subdir/{base_name}'
        assert mv_dir_res[1]['is_dir'] is False

        assert not os.path.exists(os.path.join(lb.root_dir, 'code', 'subdir'))
        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'target_dir/subdir'))

    def test_move_loaded_directory_with_full_tree(self, mock_labbook, mock_config_file, sample_src_file):
        lb = mock_labbook[2]
        FO.makedir(lb, 'code/level_1/level_2A', create_activity_record=True)
        FO.makedir(lb, 'code/level_1/level_2B', create_activity_record=True)
        FO.makedir(lb, 'code/target_dir', create_activity_record=True)
        FO.makedir(lb, 'code/target_dir/existing_dir_counted_anyway', create_activity_record=True)
        FO.makedir(lb, 'code/this-dir-must-be-ignored', create_activity_record=True)
        FO.insert_file(lb, 'code', sample_src_file, dst_path='level_1/level_2B')

        # Move "level_1" into target_dir
        results = FO.move_file(lb, 'code', 'level_1', 'target_dir')
        assert len(results) == 4

    def test_makedir_simple(self, mock_labbook):
        # Note that "score" refers to the count of .gitkeep files.
        lb = mock_labbook[2]
        long_dir = "code/non/existant/dir/should/now/be/made"
        dirs = ["code/cat_dir", "code/dog_dir", "code/mouse_dir/", "code/mouse_dir/new_dir", long_dir]
        for d in dirs:
            FO.makedir(lb, d)
            assert os.path.isdir(os.path.join(lb.root_dir, d))
            assert os.path.isfile(os.path.join(lb.root_dir, d, '.gitkeep'))
        score = 0
        for root, dirs, files in os.walk(os.path.join(lb.root_dir, 'code', 'non')):
            for f in files:
                if f == '.gitkeep':
                    score += 1
        # Ensure that count of .gitkeep files equals the number of subdirs, excluding the code dir.
        assert score == len(LabBook.make_path_relative(long_dir).split(os.sep)) - 1

    def test_makedir_record(self, mock_labbook):
        # Note that "score" refers to the count of .gitkeep files.
        lb = mock_labbook[2]
        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'test')) is False

        FO.makedir(lb, "code/test", create_activity_record=True)
        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'test')) is True
        assert lb.is_repo_clean is True

        FO.makedir(lb, "code/test2", create_activity_record=False)
        assert os.path.exists(os.path.join(lb.root_dir, 'code', 'test2')) is True
        assert lb.is_repo_clean is False

    def test_walkdir(self, mock_labbook):
        lb = mock_labbook[2]
        dirs = ["code/cat_dir", "code/dog_dir", "code/mouse_dir/", "code/mouse_dir/new_dir", "code/.hidden_dir"]
        for d in dirs:
            FO.makedir(lb, d)

        for d in ['.hidden_dir/', '', 'dog_dir', 'mouse_dir/new_dir/']:
            open('/tmp/myfile.c', 'w').write('data')
            FO.insert_file(lb, 'code', '/tmp/myfile.c', d)

        dir_walks_hidden = FO.walkdir(lb, 'code', show_hidden=True)
        assert any([os.path.basename('/tmp/myfile.c') in d['key'] for d in dir_walks_hidden])
        assert not any(['.git' in d['key'].split(os.path.sep) for d in dir_walks_hidden])
        assert not any(['.gigantum' in d['key'] for d in dir_walks_hidden])
        assert all([d['key'][0] != '/' for d in dir_walks_hidden])

        # Spot check some entries
        assert len(dir_walks_hidden) == 17
        assert dir_walks_hidden[0]['key'] == '.hidden_dir/'
        assert dir_walks_hidden[0]['is_dir'] is True
        assert dir_walks_hidden[3]['key'] == 'mouse_dir/'
        assert dir_walks_hidden[3]['is_dir'] is True
        assert dir_walks_hidden[7]['key'] == '.hidden_dir/.gitkeep'
        assert dir_walks_hidden[7]['is_dir'] is False
        assert dir_walks_hidden[14]['key'] == 'mouse_dir/new_dir/.gitkeep'
        assert dir_walks_hidden[14]['is_dir'] is False

        # Since the file is in a hidden directory, it should not be found.
        dir_walks = FO.walkdir(lb, 'code')
        # Spot check some entries
        assert len(dir_walks) == 8
        assert dir_walks[0]['key'] == 'cat_dir/'
        assert dir_walks[0]['is_dir'] is True
        assert dir_walks[1]['key'] == 'dog_dir/'
        assert dir_walks[1]['is_dir'] is True
        assert dir_walks[2]['key'] == 'mouse_dir/'
        assert dir_walks[2]['is_dir'] is True
        assert dir_walks[4]['is_dir'] is False
        assert dir_walks[5]['is_dir'] is False
        assert dir_walks[6]['is_dir'] is True
        assert dir_walks[6]['key'] == 'mouse_dir/new_dir/'
        assert dir_walks[7]['is_dir'] is False

    def test_listdir(self, mock_labbook, sample_src_file):
        def write_test_file(base, name):
            with open(os.path.join(base, name), 'wt') as f:
                f.write("Blah blah")

        lb = mock_labbook[2]
        dirs = ["code/new_dir", ".hidden_dir"]
        for d in dirs:
            FO.makedir(lb, d)
        write_test_file(lb.root_dir, 'test1.txt')
        write_test_file(lb.root_dir, 'test2.txt')
        write_test_file(lb.root_dir, '.hidden.txt')
        write_test_file(lb.root_dir, 'code/test_subdir1.txt')
        write_test_file(lb.root_dir, 'code/test_subdir2.txt')
        write_test_file(lb.root_dir, 'code/new_dir/tester.txt')

        # List just the code dir
        data = FO.listdir(lb, "code", base_path='')
        assert len(data) == 4
        assert data[0]['key'] == 'new_dir/'
        assert data[1]['key'] == 'test_subdir1.txt'
        assert data[2]['key'] == 'test_subdir2.txt'
        assert data[3]['key'] == 'untracked/'

        data = FO.listdir(lb, "input", base_path='')
        assert len(data) == 1

        # List just the code/subdir dir
        data = FO.listdir(lb, "code", base_path='new_dir')
        assert len(data) == 1
        assert data[0]['key'] == 'new_dir/tester.txt'

    def test_listdir_expect_error(self, mock_labbook, sample_src_file):
        lb = mock_labbook[2]
        with pytest.raises(ValueError):
            FO.listdir(lb, "code", base_path='blah')
