from typing import Callable, List, Dict, Any, Tuple, Optional, TYPE_CHECKING
import pickle
from typing import List, Dict, Any, Tuple, Optional

import os
from enum import Enum
import shutil
import asyncio
from collections import OrderedDict, namedtuple
from natsort import natsorted
import copy
from pathlib import Path
from stat import S_ISDIR

from gtmcore.activity import ActivityStore, ActivityRecord, ActivityDetailType, ActivityType,\
    ActivityAction, ActivityDetailRecord
from gtmcore.activity.utils import ImmutableList, DetailRecordList, TextData
from gtmcore.dataset.manifest.hash import SmartHash
from gtmcore.dataset.manifest.file import ManifestFileCache
from gtmcore.dataset.cache import get_cache_manager_class, CacheManager
from gtmcore.dataset.manifest.eventloop import get_event_loop
from gtmcore.logging import LMLogger

if TYPE_CHECKING:
    from gtmcore.dataset import Dataset

logger = LMLogger.get_logger()


class FileChangeType(Enum):
    """Enumeration representing types of file changes"""
    NOCHANGE = 0
    CREATED = 1
    MODIFIED = 2
    DELETED = 3


StatusResult = namedtuple('StatusResult', ['created', 'modified', 'deleted'])


class Manifest(object):
    """Class to handle file file manifest"""

    def __init__(self, dataset: 'Dataset', logged_in_username: Optional[str] = None) -> None:
        self.dataset = dataset
        self.logged_in_username = logged_in_username

        cache_mgr_class = get_cache_manager_class(self.dataset.client_config)
        self.cache_mgr: CacheManager = cache_mgr_class(self.dataset, logged_in_username)

        self.hasher = SmartHash(dataset.root_dir, self.cache_mgr.cache_root,
                                self.dataset.git.repo.head.commit.hexsha)

        self._manifest_io = ManifestFileCache(dataset, logged_in_username)

        # TODO: Support ignoring files
        # self.ignore_file = os.path.join(dataset.root_dir, ".gigantumignore")
        # self.ignored = self._load_ignored()

        self._legacy_manifest_file = os.path.join(self.dataset.root_dir, 'manifest', 'manifest0')

    @property
    def dataset_revision(self) -> str:
        """Property to get the current revision hash of the dataset

        Returns:
            str
        """
        return self.dataset.git.repo.head.commit.hexsha

    @property
    def current_revision_dir(self) -> str:
        """Method to return the directory containing files for the current dataset revision. If the dir doesn't exist,
        relink it (updates to a dataset will remove a revision dir, but linked datasets may still need old revisions)

        Returns:
            str
        """
        crd = self.cache_mgr.current_revision_dir
        if not os.path.exists(crd):
            self.link_revision()
        return crd

    @property
    def manifest(self) -> OrderedDict:
        """Property to get the current manifest as the union of all manifest files, with caching supported

        Returns:
            OrderedDict
        """
        return self._manifest_io.get_manifest()

    @staticmethod
    def _get_object_subdirs(object_id) -> Tuple[str, str]:
        """Get the subdirectories when accessing an object ID

        Args:
            object_id:

        Returns:

        """
        return object_id[0:8], object_id[8:16]

    def get_num_hashing_cpus(self) -> int:
        """

        Returns:

        """
        config_val = self.dataset.client_config.config['datasets']['hash_cpu_limit']
        if config_val == 'auto':
            num_cpus = os.cpu_count()
            if not num_cpus:
                num_cpus = 1
            return num_cpus
        else:
            return int(config_val)

    def dataset_to_object_path(self, dataset_path: str) -> str:
        """Helper method to compute the absolute object path from the relative dataset path

        Args:
            dataset_path: relative dataset path

        Returns:
            str
        """
        data: Optional[dict] = self.manifest.get(dataset_path)
        if not data:
            raise ValueError(f"{dataset_path} not found in Dataset manifest.")

        hash_str: str = data['h']
        level1, level2 = self._get_object_subdirs(hash_str)
        return os.path.join(self.cache_mgr.cache_root, 'objects', level1, level2, hash_str)

    def get_abs_path(self, relative_path: str) -> str:
        """Method to generate the absolute path to a file in the cache at the current revision

        Args:
            relative_path:

        Returns:

        """
        return self.hasher.get_abs_path(relative_path)

    def queue_to_push(self, obj: str, rel_path: str, revision: str) -> None:
        """Method to queue and object for push to remote storage backend

        Objects to push are stored in a file named with the revision at which the files were written. This is different
        from the revision that contains the files (after written and untracked, changes are committed and then an
        activity record is created with another commit)

        Args:
            obj: object path
            revision: revision of the dataset the object exists in
            rel_path: Objects relative file path in the dataset

        Returns:

        """
        if not os.path.exists(obj):
            raise ValueError("Object does not exist. Failed to add to push queue.")

        push_dir = os.path.join(self.cache_mgr.cache_root, 'objects', '.push')
        if not os.path.exists(push_dir):
            os.makedirs(push_dir)

        with open(os.path.join(push_dir, revision), 'at') as fh:
            fh.write(f"{rel_path},{obj}\n")

    def get_change_type(self, path) -> FileChangeType:
        """Helper method to get the type of change from the manifest/fast hash

        Args:
            path:

        Returns:

        """
        if self.hasher.is_cached(path):
            if self.hasher.has_changed_fast(path):
                result = FileChangeType.MODIFIED
            else:
                result = FileChangeType.NOCHANGE
        else:
            if path in self.manifest:
                # No fast hash, but exists in manifest. User just edited a file that hasn't been pulled
                result = FileChangeType.MODIFIED
            else:
                # No fast hash, not in manifest.
                result = FileChangeType.CREATED
        return result

    def status(self) -> StatusResult:
        """Method to compute the changes (create, modified, delete) of a dataset, comparing local state to the
        manifest and fast hash

        Returns:
            StatusResult
        """
        # TODO: think about how to send batches to get_change_type
        status: Dict[str, List] = {"created": [], "modified": [], "deleted": []}
        all_files = list()
        revision_directory = os.path.join(self.cache_mgr.cache_root, self.dataset_revision)

        for root, dirs, files in os.walk(revision_directory):
            _, folder = root.split(revision_directory)
            if len(folder) > 0:
                if folder[0] == os.path.sep:
                    folder = folder[1:]

            for d in dirs:
                # TODO: Check for ignored
                rel_path = os.path.join(folder, d) + os.path.sep  # All folders are represented with a trailing slash
                all_files.append(rel_path)
                change = self.get_change_type(rel_path)
                if change == FileChangeType.NOCHANGE:
                    continue
                elif change == FileChangeType.MODIFIED:
                    # Don't record directory modifications
                    pass
                elif change == FileChangeType.CREATED:
                    status['created'].append(rel_path)
                else:
                    raise ValueError(f"Invalid Change type: {change}")

            for file in files:
                # TODO: Check for ignored
                if file in ['.smarthash', '.DS_STORE', '.DS_Store']:
                    continue

                rel_path = os.path.join(folder, file)
                all_files.append(rel_path)
                change = self.get_change_type(rel_path)
                if change == FileChangeType.NOCHANGE:
                    continue
                elif change == FileChangeType.MODIFIED:
                    status['modified'].append(rel_path)
                elif change == FileChangeType.CREATED:
                    status['created'].append(rel_path)
                else:
                    raise ValueError(f"Invalid Change type: {change}")

        # De-dup and sort
        status['created'] = list(set(status['created']))
        status['modified'] = list(set(status['modified']))
        status['modified'] = natsorted(status['modified'])
        status['created'] = natsorted(status['created'])

        all_files = list(set(all_files))
        return StatusResult(created=status.get('created'), modified=status.get('modified'),
                            deleted=self.hasher.get_deleted_files(all_files))

    @staticmethod
    def _blocking_move_and_link(source, destination):
        """Blocking method to move a file and hard link it

        Args:
            source: source path
            destination: destination path

        Returns:

        """
        if os.path.isfile(destination):
            # Object already exists, no need to store again
            os.remove(source)
        else:
            # Move file to new object
            shutil.move(source, destination)
        # Link object back
        try:
            os.link(destination, source)
        except PermissionError:
            os.symlink(destination, source)

    async def _move_to_object_cache(self, relative_path, hash_str):
        """Method to move a file to the object cache

        Args:
            relative_path: relative path to the file
            hash_str: content hash of the file

        Returns:

        """
        source = os.path.join(self.cache_mgr.cache_root, self.dataset_revision, relative_path)
        if os.path.isfile(source):
            level1, level2 = self._get_object_subdirs(hash_str)

            os.makedirs(os.path.join(self.cache_mgr.cache_root, 'objects', level1), exist_ok=True)
            os.makedirs(os.path.join(self.cache_mgr.cache_root, 'objects', level1, level2), exist_ok=True)

            destination = os.path.join(self.cache_mgr.cache_root, 'objects', level1, level2, hash_str)

            # Move file to new object
            loop = get_event_loop()
            await loop.run_in_executor(None, self._blocking_move_and_link, source, destination)

            # Queue new object for push
            self.queue_to_push(destination, relative_path, self.dataset_revision)
        else:
            destination = source

        return destination

    def hash_files(self, update_files: List[str]) -> Tuple[List[Optional[str]], List[Optional[str]]]:
        """Method to run the update process on the manifest based on change status (optionally computing changes if
        status is not set)

        Args:
            update_files: The current change status of the dataset, of omitted, it will be computed

        Returns:
            StatusResult
        """
        # Hash Files
        loop = get_event_loop()
        hash_task = asyncio.ensure_future(self.hasher.hash(update_files))
        loop.run_until_complete(asyncio.gather(hash_task))

        # Move files into object cache and link back to the revision directory
        hash_result = hash_task.result()
        tasks = [asyncio.ensure_future(self._move_to_object_cache(f, h)) for f, h in zip(update_files, hash_result)]
        loop.run_until_complete(asyncio.gather(*tasks))

        # Update fast hash after objects have been moved/relinked
        fast_hash_result = self.hasher.fast_hash(update_files, save=True)

        return hash_result, fast_hash_result

    def update(self, status: StatusResult = None) -> StatusResult:
        """Method to run the update process on the manifest based on change status (optionally computing changes if
        status is not set)

        Args:
            status: The current change status of the dataset, of omitted, it will be computed

        Returns:
            StatusResult
        """
        if not status:
            status = self.status()

        update_files = copy.deepcopy(status.created)
        update_files.extend(status.modified)

        if update_files:
            hash_result, fast_hash_result = self.hash_files(update_files)

            # Update manifest file
            for f, h, fh in zip(update_files, hash_result, fast_hash_result):
                if not fh or not h:
                    raise ValueError(f"Failed to update manifest for {f}. File not found.")

                _, file_bytes, mtime = fh.split("||")
                self._manifest_io.add_or_update(f, h, mtime, file_bytes)

        if status.deleted:
            self.hasher.delete_fast_hashes(status.deleted)
            for relative_path in status.deleted:
                self._manifest_io.remove(relative_path)

        self._manifest_io.persist()

        return status

    def _file_info(self, key, item) -> Dict[str, Any]:
        """Method to populate file info (e.g. size, mtime, etc.) using data from the manifest

        Args:
            key: relative path to the file
            item: data from the manifest

        Returns:
            dict
        """
        abs_path = os.path.join(self.cache_mgr.cache_root, self.dataset_revision, key)
        return {'key': key,
                'size': item.get('b'),
                'is_local': os.path.exists(abs_path),
                'is_dir': True if abs_path[-1] == "/" else False,
                'modified_at': float(item.get('m'))}

    def gen_file_info(self, key) -> Dict[str, Any]:
        """Method to generate file info (e.g. size, mtime, etc.)

        Args:
            key: relative path to the file

        Returns:
            dict
        """
        abs_path = self.get_abs_path(key)
        stat = os.stat(abs_path)
        is_dir = True if S_ISDIR(stat.st_mode) else False

        return {'key': key,
                'size': str(stat.st_size) if not is_dir else '0',
                'is_local': True,
                'is_dir': is_dir,
                'modified_at': stat.st_mtime}

    def get(self, dataset_path: str) -> dict:
        """Method to get the file info for a single file from the manifest

        Args:
            dataset_path: Relative path to the object within the dataset

        Returns:
        """
        item = self.manifest.get(dataset_path)
        return self._file_info(dataset_path, item)

    def list(self, first: int = None, after_index: int = 0) -> Tuple[List[Dict[str, Any]], List[int]]:
        """

        Args:
            first:
            after_index:

        Returns:

        """
        if first:
            if first <= 0:
                raise ValueError("`first` must be greater than 0")
        if after_index:
            if after_index < 0:
                raise ValueError("`after_index` must be greater or equal than 0")

        result = list()
        indexes = list()

        if after_index != 0:
            after_index = after_index + 1

        if first is not None:
            end = min(first + after_index, len(self.manifest))
        else:
            end = len(self.manifest)

        data = list(self.manifest.items())
        for idx in range(after_index, end):
            result.append(self._file_info(data[idx][0], data[idx][1]))
            indexes.append(idx)

        return result, indexes

    def delete(self, path_list: List[str]) -> None:
        """Method to delete a list of files/folders from the dataset

        Args:
            path_list: List of relative paths in the dataset

        Returns:

        """
        revision_directory = os.path.join(self.cache_mgr.cache_root, self.dataset_revision)

        for path in path_list:
            target_path = os.path.join(revision_directory, path)
            if os.path.isdir(target_path):
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)

        self.sweep_all_changes()

    def move(self, src_path: str, dest_path: str) -> List[Dict[str, Any]]:
        """Method to move/rename a file or directory in a dataset

        Args:
            src_path: The relative path in the dataset to the source file/folder
            dest_path: The relative path in the dataset to the destination file/folder

        Returns:

        """
        revision_directory = os.path.join(self.cache_mgr.cache_root, self.dataset_revision)
        src_rel_path = self.dataset.make_path_relative(src_path.replace('..', ''))
        dest_rel_path = self.dataset.make_path_relative(dest_path.replace('..', ''))
        src_abs_path = os.path.join(revision_directory, src_rel_path)
        dest_abs_path = os.path.join(revision_directory, dest_rel_path)

        src_type = 'directory' if os.path.isdir(src_abs_path) else 'file'

        if not os.path.exists(src_abs_path):
            raise ValueError(f"No src file or folder exists at `{src_abs_path}`")

        # Move
        result_path = shutil.move(src_abs_path, dest_abs_path)
        msg = f"Moved {src_type} `{src_rel_path}` to `{dest_rel_path}`"
        previous_revision_directory = os.path.join(self.cache_mgr.cache_root, self.dataset_revision)
        self.sweep_all_changes(extra_msg=msg)

        # Update paths due to relinking
        revision_directory = os.path.join(self.cache_mgr.cache_root, self.dataset_revision)
        final_rel_path = self.dataset.make_path_relative(result_path.replace(previous_revision_directory, ''))
        dest_abs_path = os.path.join(revision_directory, final_rel_path)

        if os.path.isfile(dest_abs_path):
            manifest_data = self.manifest.get(final_rel_path)
            return [self._file_info(final_rel_path, manifest_data)]
        elif os.path.isdir(dest_abs_path):
            moved_files = list()
            moved_files.append(self.gen_file_info(final_rel_path))
            for root, dirs, files in os.walk(dest_abs_path):
                dirs.sort()
                rt = root.replace(revision_directory, '')
                rt = self.dataset.make_path_relative(rt)
                for d in dirs:
                    if d[-1] != os.path.sep:
                        d = d + '/'
                    moved_files.append(self.gen_file_info(os.path.join(rt, d)))
                for f in filter(lambda n: n != '.gitkeep', sorted(files)):
                    rel_path = os.path.join(rt, f)
                    manifest_data = self.manifest.get(rel_path)
                    moved_files.append(self._file_info(rel_path, manifest_data))
        else:
            raise ValueError("Destination path does not exist after move operation")

        return moved_files

    def create_directory(self, path: str) -> Dict[str, Any]:
        """Method to create an empty directory in a dataset

        Args:
            path: Relative path to the directory

        Returns:
            dict
        """
        relative_path = self.dataset.make_path_relative(path)
        new_directory_path = os.path.join(self.cache_mgr.cache_root, self.dataset_revision, relative_path)

        previous_revision = self.dataset_revision

        if os.path.exists(new_directory_path):
            raise ValueError(f"Directory already exists: `{relative_path}`")
        else:
            logger.info(f"Creating new empty directory in `{new_directory_path}`")

            if os.path.isdir(Path(new_directory_path).parent) is False:
                raise ValueError(f"Parent directory does not exist. Failed to create `{new_directory_path}` ")

            # create dir
            os.makedirs(new_directory_path)
            self.update()
            if relative_path not in self.manifest:
                raise ValueError("Failed to add directory to manifest")

            # Create detail record
            msg = f"Created new empty directory `{relative_path}`"
            adr = ActivityDetailRecord(ActivityDetailType.DATASET,
                                       show=False,
                                       importance=0,
                                       action=ActivityAction.CREATE,
                                       data=TextData('markdown', msg))

            commit = self.dataset.git.commit(msg)

            # Create activity record
            ar = ActivityRecord(ActivityType.DATASET,
                                message=msg,
                                linked_commit=commit.hexsha,
                                show=True,
                                importance=255,
                                detail_objects=DetailRecordList([adr]),
                                tags=ImmutableList(['directory-create']))

            # Store
            ars = ActivityStore(self.dataset)
            ars.create_activity_record(ar)

            # Relink after the commit
            self.link_revision()
            if os.path.isdir(os.path.join(self.cache_mgr.cache_root, previous_revision)):
                shutil.rmtree(os.path.join(self.cache_mgr.cache_root, previous_revision))

            return self.gen_file_info(relative_path)

    def link_revision(self) -> None:
        """Method to link all the objects in the cache to the current revision directory, so that all files are
        accessible with the correct file names.

        Note: This update the current revision in the hashing class

        Returns:
            None
        """
        current_revision = self.dataset_revision
        self.hasher.current_revision = current_revision

        revision_directory = os.path.join(self.cache_mgr.cache_root, current_revision)

        if not os.path.exists(revision_directory):
            os.makedirs(revision_directory)

        for f in self.manifest:
            hash_str = self.manifest[f].get('h')
            level1, level2 = self._get_object_subdirs(hash_str)

            target = os.path.join(revision_directory, f)
            if target[-1] == os.path.sep:
                # Create directory from manifest
                if not os.path.exists(target):
                    os.makedirs(target)
            else:
                # Link file
                source = os.path.join(self.cache_mgr.cache_root, 'objects', level1, level2, hash_str)

                target_dir = os.path.dirname(target)
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir)

                # Link if not already linked
                if not os.path.exists(target):
                    try:
                        if os.path.exists(source):
                            # Only try to link if the source object has been materialized
                            os.link(source, target)
                    except Exception as err:
                        logger.exception(err)
                        continue

        # Completely re-compute the fast hash index
        self.hasher.fast_hash_data = dict()
        self.hasher.fast_hash(list(self.manifest.keys()))

    def create_update_activity_record(self, status: StatusResult, upload: bool = False, extra_msg: str = None) -> None:
        """

        Args:
            status(StatusResult): a StatusResult object after updating the manifest
            upload(bool): flag indicating if this is a record for an upload
            extra_msg(str): any extra string to add to the activity record

        Returns:
            None
        """
        def _item_type(key):
            if key[-1] == os.path.sep:
                return 'directory'
            else:
                return 'file'

        if len(status.deleted) > 0 or len(status.created) > 0 or len(status.modified) > 0:
            # commit changed manifest file
            self.dataset.git.add_all()
            self.dataset.git.commit("Commit changes to manifest file.")

            adrs = []

            for cnt, f in enumerate(status.created):
                msg = f"Created new {_item_type(f)} `{f}`"
                adr = ActivityDetailRecord(ActivityDetailType.DATASET, show=False, importance=max(255 - cnt, 0),
                                           action=ActivityAction.CREATE, data=TextData('markdown', msg))

                adrs.append(adr)

            for cnt, f in enumerate(status.modified):
                msg = f"Modified {_item_type(f)} `{f}`"
                adr = ActivityDetailRecord(ActivityDetailType.DATASET, show=False, importance=max(255 - cnt, 0),
                                           action=ActivityAction.EDIT, data=TextData('markdown', msg))

                adrs.append(adr)

            for cnt, f in enumerate(status.deleted):
                msg = f"Deleted {_item_type(f)} `{f}`"
                adr = ActivityDetailRecord(ActivityDetailType.DATASET, show=False, importance=max(255 - cnt, 0),
                                           action=ActivityAction.DELETE, data=TextData('markdown', msg))

                adrs.append(adr)

            num_files_created = sum([_item_type(x) == "file" for x in status.created])
            num_files_modified = sum([_item_type(x) == "file" for x in status.modified])
            num_files_deleted = sum([_item_type(x) == "file" for x in status.deleted])
            upload_str = "Uploaded" if upload else ''
            nmsg = f"{upload_str} {num_files_created} new file(s). " if num_files_created > 0 else ""
            mmsg = f"{upload_str} {num_files_modified} modified file(s). " if num_files_modified > 0 else ""
            dmsg = f"{num_files_deleted} deleted file(s). " if num_files_deleted > 0 else ""

            if not nmsg and not mmsg and not dmsg:
                # You didn't edit any files, only an empty directory
                num_dirs_created = sum([_item_type(x) == "directory" for x in status.created])
                num_dirs_modified = sum([_item_type(x) == "directory" for x in status.modified])
                num_dirs_deleted = sum([_item_type(x) == "directory" for x in status.deleted])
                nmsg = f"{num_dirs_created} new folder(s). " if num_dirs_created > 0 else ""
                mmsg = f"{num_dirs_modified} modified folder(s). " if num_dirs_modified > 0 else ""
                dmsg = f"{num_dirs_deleted} deleted folder(s). " if num_dirs_deleted > 0 else ""

            message = f"{extra_msg if extra_msg else ''}" \
                      f"{nmsg}{mmsg}{dmsg}"

            ar = ActivityRecord(ActivityType.DATASET,
                                message=message,
                                show=True,
                                importance=255,
                                linked_commit=self.dataset.git.commit_hash,
                                detail_objects=DetailRecordList(adrs))

            ars = ActivityStore(self.dataset)
            ars.create_activity_record(ar)

    def sweep_all_changes(self, upload: bool = False, extra_msg: str = None,
                          status: Optional[StatusResult] = None) -> None:
        """

        Args:
            upload(bool): flag indicating if this is a record for an upload
            extra_msg(str): any extra string to add to the activity record
            status(StatusResult): a StatusResult object after updating the manifest

        Returns:

        """
        previous_revision = self.dataset_revision

        # If `status` is set, assume update() has been run already
        if not status:
            status = self.update()

        # Update manifest
        self.create_update_activity_record(status, upload=upload, extra_msg=extra_msg)

        # Re-link new revision
        self.link_revision()
        if os.path.isdir(os.path.join(self.cache_mgr.cache_root, previous_revision)):
            shutil.rmtree(os.path.join(self.cache_mgr.cache_root, previous_revision))

    def force_reload(self) -> None:
        """Method to force reloading manifest data from the filesystem

        This is useful when an update to the manifest occurs, but within a checkout context. This can happen with
        linked local datasets for example.

        Returns:
            None
        """
        self._manifest_io.evict()
        _ = self.manifest
