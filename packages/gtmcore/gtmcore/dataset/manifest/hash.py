from hashlib import blake2b
import aiofiles

from typing import List, Optional
import pickle
import os
from gtmcore.logging import LMLogger

logger = LMLogger.get_logger()


class SmartHash(object):
    """Class to handle file hashing that is operationally optimized for Gigantum"""

    def __init__(self, root_dir: str, file_cache_root: str, current_revision: str) -> None:
        self.root_dir = root_dir
        self.file_cache_root = file_cache_root
        self.current_revision = current_revision

        self.fast_hash_data = self._load_fast_hash_file()

        self.hashing_block_size = 65536

    @property
    def fast_hash_file(self):
        hash_file_dir = os.path.join(self.file_cache_root, self.current_revision)
        return os.path.join(hash_file_dir, ".smarthash")

    def _load_fast_hash_file(self) -> dict:
        """Method to load the cached fast hash file

        Returns:
            dict
        """
        if os.path.exists(self.fast_hash_file):
            with open(self.fast_hash_file, 'rb') as mf:
                return pickle.load(mf)
        else:
            return dict()

    def _save_fast_hash_file(self) -> None:
        """Method to save the cached fast hash file

        Returns:
            dict
        """
        with open(self.fast_hash_file, 'wb') as mf:
            pickle.dump(self.fast_hash_data, mf, pickle.HIGHEST_PROTOCOL)

    def get_abs_path(self, relative_path: str) -> str:
        """Method to generate the absolute path to the file

        Args:
            relative_path:

        Returns:

        """
        if relative_path[0] == '/':
            relative_path = relative_path[1:]

        return os.path.join(self.file_cache_root, self.current_revision, relative_path)

    def is_cached(self, path: str) -> bool:
        """Method to check if a file has been loaded into the file cache

        Args:
            path: relative path to the file in the dataset

        Returns:

        """
        return path in self.fast_hash_data

    def has_changed_fast(self, path: str) -> bool:
        """Method to check if a file has changed according to the fast hash

        Args:
            path: Relative path to the file in the dataset

        Returns:

        """
        return self._compute_fast_hash(path) != self.fast_hash_data.get(path)

    def get_deleted_files(self, file_list: List[str]) -> list:
        """Method to list files that have previously been in the fast hash (exist locally) and have been removed

        Args:
            file_list: List of relative paths to files in the dataset

        Returns:

        """
        return sorted(list(set(self.fast_hash_data.keys()).difference(file_list)))

    def delete_fast_hashes(self, file_list: List[str]) -> None:
        """Method to remove fast hashes from the stored hash file

        Args:
            file_list: list of relative paths to remove from the fast hash data

        Returns:

        """
        for f in file_list:
            del self.fast_hash_data[f]

        self._save_fast_hash_file()

    def _compute_fast_hash(self, relative_path: str) -> Optional[str]:
        """

        Note, the delimiter `||` is used as it's unlikely to be in a path. Hash structure:

        relative file path || size in bytes || mtime

        Args:
            relative_path:

        Returns:
            str
        """
        abs_path = self.get_abs_path(relative_path)
        fast_hash_val = None
        if os.path.exists(abs_path):
            file_info = os.stat(abs_path)
            if os.path.isdir(abs_path):
                # Always set directory size to 0 for uniformity across file systems
                size = 0
            else:
                size = file_info.st_size
            fast_hash_val = f"{relative_path}||{size}||{file_info.st_mtime}"
        return fast_hash_val

    def fast_hash(self, path_list: list, save: bool = True) -> List[Optional[str]]:
        """

        Note, the delimiter `||` is used as it's unlikely to be in a path. Hash structure:

        relative file path || size in bytes || mtime

        Args:
            path_list:
            save:

        Returns:

        """
        fast_hash_result: List[Optional[str]] = list()
        if len(path_list) > 0:
            fast_hash_result = [self._compute_fast_hash(x) for x in path_list]

            if save:
                for p, h in zip(path_list, fast_hash_result):
                    if h:
                        self.fast_hash_data[p] = h

                self._save_fast_hash_file()

        return fast_hash_result

    async def compute_file_hash(self, path: str, blocksize: int = 4096) -> Optional[str]:
        """Method to compute the black2b hash for the provided file

        Args:
            path: Relative path to the file
            blocksize: Blocksize to use when reading the file and computing the hash

        Returns:
            str
        """
        h = blake2b()
        try:
            abs_path = self.get_abs_path(path)
            if os.path.isfile(abs_path):
                async with aiofiles.open(abs_path, 'rb') as fh:
                    chunk = await fh.read(blocksize)
                    while chunk:
                        h.update(chunk)
                        chunk = await fh.read(blocksize)
            elif os.path.isdir(abs_path):
                # If a directory, just hash the path as an alternative
                h.update(abs_path.encode('utf-8'))
            else:
                return None
        except Exception as err:
            logger.exception(err)
            return None

        return h.hexdigest()

    async def hash(self, path_list: List[str]) -> List[Optional[str]]:
        """Method to compute the blake2b hash of a file's contents.

        Args:
            path_list:

        Returns:
            list
        """
        hash_result_list: List[Optional[str]] = [await self.compute_file_hash(path,
                                                 self.hashing_block_size) for path in path_list]

        return hash_result_list
