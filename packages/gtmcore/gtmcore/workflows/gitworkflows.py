from abc import ABC, abstractmethod
import os
import time
from enum import Enum
import glob
from typing import Optional, Callable, cast, List
from humanfriendly import format_size

from gtmcore.configuration.utils import call_subprocess
from gtmcore.gitlib import RepoLocation
from gtmcore.logging import LMLogger
from gtmcore.labbook import LabBook
from gtmcore.labbook.schemas import CURRENT_SCHEMA as CURRENT_LABBOOK_SCHEMA
from gtmcore.workflows import gitworkflows_utils
from gtmcore.exceptions import GigantumException
from gtmcore.inventory import Repository
from gtmcore.inventory.inventory import InventoryManager
from gtmcore.dataset import Dataset
from gtmcore.inventory.branching import BranchManager, MergeError
from gtmcore.dataset.manifest import Manifest
from gtmcore.dataset.io.manager import IOManager
from gtmcore.dispatcher import Dispatcher
import gtmcore.dispatcher.dataset_jobs
from gtmcore.dataset.io.job import BackgroundUploadJob

logger = LMLogger.get_logger()


class GitWorkflowException(GigantumException):
    pass


class MergeOverride(Enum):
    OURS = 'ours'
    THEIRS = 'theirs'
    ABORT = 'abort'


class GitWorkflow(ABC):
    """Manages all aspects of interaction with Git remote server
    """

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    @property
    def remote(self) -> Optional[str]:
        return self.repository.remote

    @classmethod
    @abstractmethod
    def import_from_remote(cls, remote: RepoLocation, username: str) -> 'GitWorkflow':
        pass

    def garbagecollect(self):
        """ Run a `git gc` on the repository. """
        gitworkflows_utils.git_garbage_collect(self.repository)

    def publish(self, username: str, access_token: Optional[str] = None, remote: str = "origin",
                public: bool = False, feedback_callback: Callable = lambda _ : None,
                id_token: Optional[str] = None) -> None:
        """ Publish this repository to the remote GitLab instance. This runs in a bg job

        Args:
            username: Subject username
            access_token: bearer token for currently logged in user
            remote: Name of Git remote (always "origin" for now).
            public: Allow public read access
            feedback_callback: Callback to give user-facing realtime feedback
            id_token: id token for currently logged in user
        Returns:
            None
        """
        logger.info(f"Publishing {str(self.repository)} for user {username} to remote {remote}")
        if self.remote:
            raise GitWorkflowException("Cannot publish Labbook when remote already set.")

        branch_mgr = BranchManager(self.repository, username=username)
        if branch_mgr.active_branch != branch_mgr.workspace_branch:
            raise GitWorkflowException(f"Must be on branch {branch_mgr.workspace_branch} to publish")

        try:
            self.repository.sweep_uncommitted_changes()
            vis = "public" if public is True else "private"
            gitworkflows_utils.create_remote_gitlab_repo(repository=self.repository, username=username,
                                                         access_token=access_token, id_token=id_token,
                                                         visibility=vis)
            gitworkflows_utils.publish_to_remote(repository=self.repository, username=username,
                                                 remote=remote, feedback_callback=feedback_callback)
        except Exception as e:
            feedback_callback(f"ERROR: {str(e)}")
            logger.error(f"Publish failed {e}: {str(self.repository)} may be in corrupted Git state!")
            call_subprocess(['git', 'reset', '--hard'], cwd=self.repository.root_dir)
            raise Exception(f"An error occurred while publishing. "
                            f"View details for more information and try again. You may need to refresh the page and"
                            f" try to sync again.")

    def sync(self, username: str, remote: str = "origin", override: MergeOverride = MergeOverride.ABORT,
             feedback_callback: Callable = lambda _: None, pull_only: bool = False,
             access_token: Optional[str] = None, id_token: Optional[str] = None) -> int:
        """ Sync with remote GitLab repo (i.e., pull any upstream changes and push any new changes). Following
        a sync operation both the local repo and remote should be at the same revision. This runs in a bg job

        Args:
            username: Subject user
            remote: Name of remote (usually only origin for now)
            override: In the event of conflict, select merge method (mine/theirs/abort)
            pull_only: If true, do not push back after doing a pull.
            feedback_callback: Used to give periodic feedback
            access_token: current logged in users's access token
            id_token: current logged in users's id token

        Returns:
            Integer number of commits pulled down from remote.
        """
        try:
            updates_cnt = gitworkflows_utils.sync_branch(self.repository, username=username,
                                                         override=override.value, pull_only=pull_only,
                                                         feedback_callback=feedback_callback)
        except MergeError:
            raise
        except Exception as err:
            feedback_callback(f"ERROR: {str(err)}")
            raise Exception(f"An error occurred while syncing. View details for more information and try again.")

        return updates_cnt

    def reset(self, username: str) -> None:
        """ Perform a Git reset to undo all local changes"""
        bm = BranchManager(self.repository, username)
        if self.remote and bm.active_branch in bm.branches_remote:
            self.repository.git.fetch()
            self.repository.sweep_uncommitted_changes()
            call_subprocess(['git', 'reset', '--hard', f'origin/{bm.active_branch}'],
                            cwd=self.repository.root_dir)
            call_subprocess(['git', 'clean', '-fd'], cwd=self.repository.root_dir)
            self.repository.git.clear_checkout_context()


class LabbookWorkflow(GitWorkflow):
    @property
    def labbook(self):
        return cast(LabBook, self.repository)

    @classmethod
    def import_from_remote(cls, remote: RepoLocation, username: str) -> 'LabbookWorkflow':
        """Take a URL of a remote Labbook and manifest it locally on this system. """

        try:
            inv_manager = InventoryManager()
            repo = gitworkflows_utils.clone_repo(remote_url=remote.remote_location, username=username,
                                                 owner=remote.owner,
                                                 load_repository=inv_manager.load_labbook_from_directory,
                                                 put_repository=inv_manager.put_labbook)
            logger.info(f"Imported remote Project {str(repo)} on branch {repo.active_branch}")
            wf = cls(repo)

            # Check for linked datasets, and schedule auto-imports
            gitworkflows_utils.process_linked_datasets(wf.labbook, username)

            return wf
        except Exception as e:
            logger.exception(e)
            raise

    def should_migrate(self) -> bool:
        """
        Indicate whether a migration should be performed

        Only looks at LOCAL details.
        """
        bm = BranchManager(self.labbook)
        if 'gm.workspace' not in bm.active_branch:
            return False

        if 'master' not in bm.branches_local:
            return True

        logmsgs = call_subprocess('git log master --oneline --pretty=format:"%s"'.split(),
                                  cwd=self.labbook.root_dir).split('\n')
        if '"Migrate schema to 2"' in logmsgs:
            return False

        return True

    def migrate(self) -> bool:
        """ Migrate the given LabBook to the most recent schema AND branch version.

        Returns:
            Boolean indicating whether a migration was performed (False if already up-to-date)
        """
        if self.repository.schema == CURRENT_LABBOOK_SCHEMA:
            logger.info(f"{str(self.labbook)} already migrated.")
            return False

        if 'gm.workspace' not in BranchManager(self.labbook).active_branch:
            raise GitWorkflowException('Must be on a gm.workspace branch to migrate')

        im = InventoryManager()
        gitworkflows_utils.migrate_labbook_branches(self.labbook)
        self.repository = im.load_labbook_from_directory(self.labbook.root_dir)

        gitworkflows_utils.migrate_labbook_schema(self.labbook)
        self.repository = im.load_labbook_from_directory(self.labbook.root_dir)

        added_missing = im.ensure_untracked_spaces(self.repository)
        if not added_missing:
            # No missing untracked folders were added, so we need to do the sweep here
            self.labbook.sweep_uncommitted_changes()

        # Pushes up the new master branch
        if self.repository.has_remote:
            self.sync(username='')

        return True

    def checkout(self, username: str, branch_name: str) -> None:
        """Workflow method to checkout a branch in a Project, and if a new linked dataset has been introduced,
        automatically import it.

        Args:
            username: Current logged in username
            branch_name: name of the branch to checkout

        Returns:
            None
        """
        # Checkout the branch
        bm = BranchManager(self.labbook, username=username)
        bm.workon_branch(branch_name=branch_name)

        # Update linked datasets inside the Project, clean them out if needed, and schedule auto-imports
        gitworkflows_utils.process_linked_datasets(self.labbook, username)

    def sync(self, username: str, remote: str = "origin", override: MergeOverride = MergeOverride.ABORT,
             feedback_callback: Callable = lambda _: None, pull_only: bool = False,
             access_token: Optional[str] = None, id_token: Optional[str] = None) -> int:
        """ Sync with remote GitLab repo (i.e., pull any upstream changes and push any new changes). Following
        a sync operation both the local repo and remote should be at the same revision.

        Args:
            username: Subject user
            remote: Name of remote (usually only origin for now)
            override: In the event of conflict, select merge method (mine/theirs/abort)
            pull_only: If true, do not push back after doing a pull.
            feedback_callback: Used to give periodic feedback
            access_token: User's current access token
            id_token: User's current ID token

        Returns:
            Integer number of commits pulled down from remote.
        """
        updates_cnt = super().sync(username, remote, override=override, feedback_callback=feedback_callback,
                                   pull_only=pull_only, access_token=access_token, id_token=id_token)

        # Update linked datasets inside the Project, clean them out if needed, and schedule auto-imports
        gitworkflows_utils.process_linked_datasets(self.labbook, username)

        return updates_cnt

    def reset(self, username: str) -> None:
        """ Perform a Git reset to undo all local changes based on remote branch state

        Args:
            username: current logged in username

        Returns:
            None
        """
        super().reset(username)

        # Update linked datasets inside the Project, clean them out if needed, and schedule auto-imports
        gitworkflows_utils.process_linked_datasets(self.labbook, username)


class DatasetWorkflow(GitWorkflow):
    @property
    def dataset(self):
        return cast(Dataset, self.repository)

    @classmethod
    def import_from_remote(cls, remote: RepoLocation, username: str) -> 'DatasetWorkflow':
        """Take a URL of a remote Dataset and manifest it locally on this system. """
        inv_manager = InventoryManager()
        repo = gitworkflows_utils.clone_repo(remote_url=remote.remote_location, username=username, owner=remote.owner,
                                             load_repository=inv_manager.load_dataset_from_directory,
                                             put_repository=inv_manager.put_dataset)
        return cls(repo)

    def _push_dataset_objects(self, logged_in_username: str,
                              feedback_callback: Callable, access_token, id_token) -> None:
        """Method to schedule a push operta

        Args:
            logged_in_username:
            feedback_callback:
            access_token:
            id_token:

        Returns:

        """
        dispatcher_obj = Dispatcher()

        try:
            self.dataset.backend.set_default_configuration(logged_in_username, access_token, id_token)
            m = Manifest(self.dataset, logged_in_username)
            iom = IOManager(self.dataset, m)

            obj_batches, total_bytes, num_files = iom.compute_push_batches()

            if obj_batches:
                # Schedule jobs for batches
                bg_jobs = list()
                for objs in obj_batches:
                    job_kwargs = {
                        'objs': objs,
                        'logged_in_username': logged_in_username,
                        'access_token': access_token,
                        'id_token': id_token,
                        'dataset_owner': self.dataset.namespace,
                        'dataset_name': self.dataset.name
                    }
                    job_metadata = {'dataset': f"{logged_in_username}|{self.dataset.namespace}|{self.dataset.name}",
                                    'method': 'pull_objects'}

                    feedback_callback(f"Preparing to upload {num_files} files. Please wait...")
                    job_key = dispatcher_obj.dispatch_task(method_reference=gtmcore.dispatcher.dataset_jobs.push_dataset_objects,
                                                           kwargs=job_kwargs,
                                                           metadata=job_metadata,
                                                           persist=True)
                    bg_jobs.append(BackgroundUploadJob(dispatcher_obj, objs, job_key))
                    logger.info(f"Schedule dataset object upload job for"
                                f" {logged_in_username}/{self.dataset.namespace}/{self.dataset.name} with"
                                f" {len(objs)} objects to upload")

                while sum([(x.is_complete or x.is_failed) for x in bg_jobs]) != len(bg_jobs):
                    # Refresh all job statuses and update status feedback
                    [j.refresh_status() for j in bg_jobs]
                    total_completed_bytes = sum([j.completed_bytes for j in bg_jobs])
                    if total_completed_bytes > 0:
                        pc = (float(total_completed_bytes) / float(total_bytes)) * 100
                        feedback_callback(f"Please wait - Uploading {num_files} files ({format_size(total_completed_bytes)}"
                                          f" of {format_size(total_bytes)}) - {round(pc)}% complete",
                                          percent_complete=pc)
                    time.sleep(1)

                # if you get here, all jobs are done or failed.
                # Remove all the push files so they can be regenerated if needed
                for f in glob.glob(f'{iom.push_dir}/*'):
                    os.remove(f)

                # Aggregate failures if they exist
                failure_keys: List[str] = list()
                for j in bg_jobs:
                    if j.is_failed:
                        # Background job hard failed. Assume entire batch should get re-uploaded
                        for obj in j.objs:
                            failure_keys.append(f"{obj.dataset_path} at {obj.revision[0:8]}")
                            m.queue_to_push(obj.object_path, obj.dataset_path, obj.revision)
                    else:
                        for obj in j.get_failed_objects():
                            # Some individual objects failed
                            failure_keys.append(f"{obj.dataset_path} at {obj.revision[0:8]}")
                            m.queue_to_push(obj.object_path, obj.dataset_path, obj.revision)

                # Set final status for UI
                if len(failure_keys) == 0:
                    feedback_callback(f"Upload complete!", percent_complete=100, has_failures=False)
                else:
                    failure_str = "\n".join(failure_keys)
                    failure_detail_str = f"Files that failed to upload:\n{failure_str}"
                    feedback_callback("", percent_complete=100, has_failures=True, failure_detail=failure_detail_str)

                # Finish up by linking everything just in case
                iom.manifest.link_revision()

                if len(failure_keys) > 0:
                    # If any downloads failed, exit non-zero to the UI knows there was an error
                    raise IOError(
                        f"{len(failure_keys)} file(s) failed to upload. Check message detail for more information"
                        " and try to sync again.")
        except Exception as err:
            logger.exception(err)
            raise

    def publish(self, username: str, access_token: Optional[str] = None, remote: str = "origin",
                public: bool = False, feedback_callback: Callable = lambda _ : None,
                id_token: Optional[str] = None):
        super().publish(username, access_token, remote, public, feedback_callback, id_token)
        self._push_dataset_objects(username, feedback_callback, access_token, id_token)

    def sync(self, username: str, remote: str = "origin", override: MergeOverride = MergeOverride.ABORT,
             feedback_callback: Callable = lambda _ : None, pull_only: bool = False,
             access_token: Optional[str] = None, id_token: Optional[str] = None):
        v = super().sync(username, remote, override, feedback_callback, pull_only,
                         access_token, id_token)
        self._push_dataset_objects(username, feedback_callback, access_token, id_token)

        # Invalidate manifest cached data because the manifest can change on sync
        manifest = Manifest(self.dataset, username)
        manifest.force_reload()
        return v
