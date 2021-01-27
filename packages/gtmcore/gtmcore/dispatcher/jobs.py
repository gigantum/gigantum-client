import importlib
import json
import os
import time
from typing import Optional
import shutil

from rq import get_current_job

from gtmcore.activity.monitors.devenv import DevEnvMonitorManager
from gtmcore.container import container_for_context
from gtmcore.labbook import LabBook
from gtmcore.gitlib import RepoLocation

from gtmcore.inventory.inventory import InventoryManager, InventoryException
from gtmcore.inventory.branching import MergeError, UI_MERGE_CONFLICT_STRING
from gtmcore.inventory import Repository

from gtmcore.environment import RepositoryManager
from gtmcore.environment.repository import RepositoryLock
from gtmcore.logging import LMLogger
from gtmcore.workflows import ZipExporter, LabbookWorkflow, DatasetWorkflow, MergeOverride
from gtmcore.workflows.gitworkflows_utils import handle_git_feedback

from gtmcore.dataset.storage.backend import UnmanagedStorageBackend


# PLEASE NOTE -- No global variables!
#
# None of the following methods can use global variables.
# ANY use of globals will cause the following methods to fail.


def publish_repository(repository: Repository, username: str, access_token: str,
                       remote: Optional[str] = None, public: bool = False, id_token: str = None) -> None:
    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting publish_repository({str(repository)})")

    def update_feedback(msg: str, has_failures: Optional[bool] = None, failure_detail: Optional[str] = None,
                        percent_complete: Optional[float] = None):
        """Method to update the job's metadata and provide feedback to the UI"""
        current_job = get_current_job()
        if not current_job:
            return
        if has_failures:
            current_job.meta['has_failures'] = has_failures
        if failure_detail:
            current_job.meta['failure_detail'] = failure_detail
        if percent_complete:
            current_job.meta['percent_complete'] = percent_complete

        if 'feedback' not in current_job.meta:
            current_job.meta['feedback'] = handle_git_feedback("", msg)
        else:
            current_job.meta['feedback'] = handle_git_feedback(current_job.meta['feedback'], msg)
        current_job.save_meta()

    update_feedback("Publish task in queue")
    with repository.lock():
        if isinstance(repository, LabBook):
            wf = LabbookWorkflow(repository)
        else:
            wf = DatasetWorkflow(repository)  # type: ignore
        wf.publish(username=username, access_token=access_token, remote=remote or "origin",
                   public=public, feedback_callback=update_feedback, id_token=id_token)


def sync_repository(repository: Repository, username: str, override: MergeOverride,
                    remote: str = "origin", access_token: str = None,
                    pull_only: bool = False, id_token: str = None) -> int:
    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting sync_repository({str(repository)})")

    def update_feedback(msg: str, has_failures: Optional[bool] = None, failure_detail: Optional[str] = None,
                        percent_complete: Optional[float] = None):
        """Method to update the job's metadata and provide feedback to the UI"""
        current_job = get_current_job()
        if not current_job:
            return
        if has_failures:
            current_job.meta['has_failures'] = has_failures
        if failure_detail:
            current_job.meta['failure_detail'] = failure_detail
        if percent_complete:
            current_job.meta['percent_complete'] = percent_complete

        if 'feedback' not in current_job.meta:
            current_job.meta['feedback'] = handle_git_feedback("", msg)
        else:
            current_job.meta['feedback'] = handle_git_feedback(current_job.meta['feedback'], msg)
        current_job.save_meta()

    try:
        update_feedback("Sync task in queue")
        with repository.lock():
            if isinstance(repository, LabBook):
                wf = LabbookWorkflow(repository)
            else:
                wf = DatasetWorkflow(repository)  # type: ignore
            cnt = wf.sync(username=username, remote=remote, override=override,
                          feedback_callback=update_feedback, access_token=access_token,
                          id_token=id_token, pull_only=pull_only)
        logger.info(f"(Job {p} Completed sync_repository with cnt={cnt}")
        return cnt
    except MergeError as err:
        # When sending the merge error up, we must set this special string so the
        # UI pops up the merge conflict modal
        raise MergeError(f"{UI_MERGE_CONFLICT_STRING} - {err}")


def import_labbook_from_remote(remote_url: str, username: str) -> str:
    """Return the root directory of the newly imported Project

    Args:
        remote_url: Canonical world-facing URI, like "https://repo.domain/owner/project". This will be converted to the
          actual network location for our repository, like "https://username@repo.domain/owner/project.git/", as
          robustly as we can manage.
        username: username for currently logged in user

    Returns:
        Path to project root directory
    """
    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting import_labbook_from_remote({remote_url}, {username})")

    def update_meta(msg):
        job = get_current_job()
        if not job:
            return
        if 'feedback' not in job.meta:
            job.meta['feedback'] = handle_git_feedback("", msg)
        else:
            job.meta['feedback'] = handle_git_feedback(job.meta['feedback'], msg)

        job.save_meta()

    remote = RepoLocation(remote_url, username)
    update_meta(f"Importing Project from {remote.owner_repo!r}...")

    try:
        wf = LabbookWorkflow.import_from_remote(remote, username)
    except Exception as e:
        update_meta(f"Could not import Project from {remote.remote_location}.")
        logger.exception(f"(Job {p}) Error on import_labbook_from_remote: {e}")
        raise

    update_meta(f"Imported Project {wf.labbook.name}!")
    return wf.labbook.root_dir


def export_labbook_as_zip(labbook_path: str, lb_export_directory: str) -> str:
    """Return path to archive file of exported labbook. """
    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting export_labbook_as_zip({labbook_path})")

    try:
        lb = InventoryManager().load_labbook_from_directory(labbook_path)
        with lb.lock():
            path = ZipExporter.export_labbook(lb.root_dir, lb_export_directory)
        return path
    except Exception as e:
        logger.exception(f"(Job {p}) Error on export_labbook_as_zip: {e}")
        raise


def export_dataset_as_zip(dataset_path: str, ds_export_directory: str) -> str:
    """Return path to archive file of exported dataset. """
    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting export_dataset_as_zip({dataset_path})")

    try:
        ds = InventoryManager().load_dataset_from_directory(dataset_path)
        with ds.lock():
            path = ZipExporter.export_dataset(ds.root_dir, ds_export_directory)
        return path
    except Exception as e:
        logger.exception(f"(Job {p}) Error on export_dataset_as_zip: {e}")
        raise


def import_labboook_from_zip(archive_path: str, username: str, owner: str) -> str:
    """Method to import a labbook from a zip file

    Args:
        archive_path(str): Path to the uploaded zip
        username(str): Username
        owner(str): Owner username

    Returns:
        str: directory path of imported labbook
    """

    def update_meta(msg):
        job = get_current_job()
        if not job:
            return
        job.meta['feedback'] = msg
        job.save_meta()

    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting import_labbook_from_zip(archive_path={archive_path},"
                f"username={username}, owner={owner})")

    try:
        lb = ZipExporter.import_labbook(archive_path, username, owner,
                                        update_meta=update_meta)
        return lb.root_dir
    except Exception as e:
        logger.exception(f"(Job {p}) Error on import_labbook_from_zip({archive_path}): {e}")
        raise
    finally:
        if os.path.exists(archive_path):
            os.remove(archive_path)


def import_dataset_from_zip(archive_path: str, username: str, owner: str) -> str:
    """Method to import a dataset from a zip file

    Args:
        archive_path(str): Path to the uploaded zip
        username(str): Username
        owner(str): Owner username

    Returns:
        str: directory path of imported labbook
    """

    def update_meta(msg):
        job = get_current_job()
        if not job:
            return
        job.meta['feedback'] = msg
        job.save_meta()

    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting import_dataset_from_zip(archive_path={archive_path},"
                f"username={username}, owner={owner})")

    try:
        lb = ZipExporter.import_dataset(archive_path, username, owner,
                                        update_meta=update_meta)
        return lb.root_dir
    except Exception as e:
        logger.exception(f"(Job {p}) Error on import_dataset_from_zip({archive_path}): {e}")
        raise
    finally:
        if os.path.exists(archive_path):
            os.remove(archive_path)


def build_labbook_image(path: str, username: str, tag: Optional[str] = None, nocache: bool = False) -> str:
    """Return a docker image ID of given LabBook.

    Args:
        path: Pass-through arg to labbook root.
        username: Username of active user.
        tag: Pass-through arg to tag of docker image.
        nocache(bool): Pass-through arg to docker build.

    Returns:
        Docker image ID
    """
    logger = LMLogger.get_logger()
    logger.info(f"Starting build_labbook_image({path}, {username}, {tag}, {nocache}) in pid {os.getpid()}")

    user_defined_ca_dir = os.path.join(path, '.gigantum', 'env', 'certificates')

    try:
        job = get_current_job()
        if job:
            job.meta['pid'] = os.getpid()
            job.save_meta()

        def save_metadata_callback(line: str) -> None:
            try:
                if not line:
                    return
                job.meta['feedback'] = (job.meta.get('feedback') or '') + line
                job.save_meta()
            except Exception as e:
                logger.error(e)

        save_metadata_callback("Build task in queue\n")
        container_ops = container_for_context(username, path=path, override_image_name=tag)
        container_ops.build_image(nocache=nocache, feedback_callback=save_metadata_callback)

        # Remove all user defined CA certificates. We do not want to leak these by any accidental copy or commit!
        if os.path.isdir(user_defined_ca_dir):
            shutil.rmtree(user_defined_ca_dir)

        logger.info(f"Completed build_labbook_image in pid {os.getpid()}: {container_ops.image_tag}")
        # This used to return and image ID, but this nametag should work equally well for all docker-py operations
        # Also note that we can be certain image_tag is not None, but we add some logic for the type-checker
        return container_ops.image_tag or ''
    except Exception as e:
        if os.path.isdir(user_defined_ca_dir):
            # Remove all user defined CA certificates. We do not want to leak these by any accidental copy or commit!
            shutil.rmtree(user_defined_ca_dir)
        logger.error(f"Error on build_labbook_image in pid {os.getpid()}: {e}")
        raise


def run_dev_env_monitor(dev_env_name, key) -> int:
    """Run method to check if new Activity Monitors for a given dev env need to be started/stopped

        Args:
            dev_env_name(str): Name of the dev env to monitor
            key(str): The unique string used as the key in redis to track this DevEnvMonitor instance

    Returns:
        0 to indicate no failure
    """

    logger = LMLogger.get_logger()
    logger.debug("Checking Dev Env `{}` for activity monitors in PID {}".format(dev_env_name, os.getpid()))

    try:
        demm = DevEnvMonitorManager()
        dev_env = demm.get_monitor_instance(dev_env_name)
        if not dev_env:
            raise ValueError('dev_env is None')
        dev_env.run(key)
        return 0
    except Exception as e:
        logger.error("Error on run_dev_env_monitor in pid {}: {}".format(os.getpid(), e))
        raise e


def start_and_run_activity_monitor(module_name, class_name, user, owner, labbook_name, monitor_key, author_name,
                                   author_email, session_metadata):
    """Run method to run the activity monitor. It is a long running job.

        Args:


    Returns:
        0 to indicate no failure
    """
    logger = LMLogger.get_logger()
    logger.info("Starting Activity Monitor `{}` in PID {}".format(class_name, os.getpid()))

    try:
        # Import the monitor class
        m = importlib.import_module(module_name)
        # get the class
        monitor_cls = getattr(m, class_name)

        # Instantiate monitor class
        monitor = monitor_cls(user, owner, labbook_name, monitor_key,
                              author_name=author_name, author_email=author_email)

        # Start the monitor
        monitor.start(session_metadata)

        return 0
    except Exception as e:
        logger.error("Error on start_and_run_activity_monitor in pid {}: {}".format(os.getpid(), e))
        raise e


def update_unmanaged_dataset_from_remote(logged_in_username: str, access_token: str, id_token: str,
                                         dataset_owner: str, dataset_name: str) -> None:
    """Method to update/populate an unmanaged dataset from its remote automatically

    Args:
        logged_in_username: username for the currently logged in user
        access_token: bearer token
        id_token: identity token
        dataset_owner: Owner of the dataset containing the files to download
        dataset_name: Name of the dataset containing the files to download

    Returns:

    """
    def update_meta(msg):
        job = get_current_job()
        if not job:
            return
        if 'feedback' not in job.meta:
            job.meta['feedback'] = msg
        else:
            job.meta['feedback'] = job.meta['feedback'] + f'\n{msg}'
        job.save_meta()

    logger = LMLogger.get_logger()

    try:
        p = os.getpid()
        logger.info(f"(Job {p}) Starting update_unmanaged_dataset_from_remote(logged_in_username={logged_in_username},"
                    f"dataset_owner={dataset_owner}, dataset_name={dataset_name}")

        im = InventoryManager()
        ds = im.load_dataset(logged_in_username, dataset_owner, dataset_name)

        ds.namespace = dataset_owner
        ds.backend.set_default_configuration(logged_in_username, access_token, id_token)

        if not isinstance(ds.backend, UnmanagedStorageBackend):
            raise ValueError("Can only auto-update unmanaged dataset types")

        if not ds.backend.can_update_from_remote:
            raise ValueError("Storage backend cannot update automatically from remote.")

        ds.backend.update_from_remote(ds, update_meta)

    except Exception as err:
        logger.exception(err)
        raise


def verify_dataset_contents(logged_in_username: str, access_token: str, id_token: str,
                            dataset_owner: str, dataset_name: str,
                            labbook_owner: Optional[str] = None, labbook_name: Optional[str] = None) -> None:
    """Method to update/populate an unmanaged dataset from it local state

    Args:
        logged_in_username: username for the currently logged in user
        access_token: bearer token
        id_token: identity token
        dataset_owner: Owner of the dataset containing the files to download
        dataset_name: Name of the dataset containing the files to download
        labbook_owner: Owner of the labbook if this dataset is linked
        labbook_name: Name of the labbook if this dataset is linked

    Returns:
        None
    """
    job = get_current_job()

    def update_meta(msg):
        if not job:
            return
        if 'feedback' not in job.meta:
            job.meta['feedback'] = msg
        else:
            job.meta['feedback'] = job.meta['feedback'] + f'\n{msg}'
        job.save_meta()

    logger = LMLogger.get_logger()

    try:
        p = os.getpid()
        logger.info(f"(Job {p}) Starting verify_dataset_contents(logged_in_username={logged_in_username},"
                    f"dataset_owner={dataset_owner}, dataset_name={dataset_name},"
                    f"labbook_owner={labbook_owner}, labbook_name={labbook_name}")

        im = InventoryManager()
        if labbook_owner is not None and labbook_name is not None:
            # This is a linked dataset, load repo from the Project
            lb = im.load_labbook(logged_in_username, labbook_owner, labbook_name)
            dataset_dir = os.path.join(lb.root_dir, '.gigantum', 'datasets', dataset_owner, dataset_name)
            ds = im.load_dataset_from_directory(dataset_dir)
        else:
            # this is a normal dataset. Load repo from working dir
            ds = im.load_dataset(logged_in_username, dataset_owner, dataset_name)

        ds.namespace = dataset_owner
        ds.backend.set_default_configuration(logged_in_username, access_token, id_token)

        result = ds.backend.verify_contents(ds, update_meta)
        job.meta['modified_keys'] = result

    except Exception as err:
        logger.exception(err)
        raise


def update_unmanaged_dataset_from_local(logged_in_username: str, access_token: str, id_token: str,
                                        dataset_owner: str, dataset_name: str) -> None:
    """Method to update/populate an unmanaged dataset from it local state

    Args:
        logged_in_username: username for the currently logged in user
        access_token: bearer token
        id_token: identity token
        dataset_owner: Owner of the dataset containing the files to download
        dataset_name: Name of the dataset containing the files to download

    Returns:

    """
    def update_meta(msg):
        job = get_current_job()
        if not job:
            return
        if 'feedback' not in job.meta:
            job.meta['feedback'] = msg
        else:
            job.meta['feedback'] = job.meta['feedback'] + f'\n{msg}'
        job.save_meta()

    logger = LMLogger.get_logger()

    try:
        p = os.getpid()
        logger.info(f"(Job {p}) Starting update_unmanaged_dataset_from_local(logged_in_username={logged_in_username},"
                    f"dataset_owner={dataset_owner}, dataset_name={dataset_name}")

        im = InventoryManager()
        ds = im.load_dataset(logged_in_username, dataset_owner, dataset_name)

        ds.namespace = dataset_owner
        ds.backend.set_default_configuration(logged_in_username, access_token, id_token)

        if not isinstance(ds.backend, UnmanagedStorageBackend):
            raise ValueError("Can only auto-update unmanaged dataset types")

        ds.backend.update_from_local(ds, update_meta, verify_contents=True)

    except Exception as err:
        logger.exception(err)
        raise


def clean_dataset_file_cache(logged_in_username: str, dataset_owner: str, dataset_name: str,
                             cache_location: str) -> None:
    """Method to import a dataset from a zip file

    Args:
        logged_in_username: username for the currently logged in user
        dataset_owner: Owner of the labbook if this dataset is linked
        dataset_name: Name of the labbook if this dataset is linked
        cache_location: Absolute path to the file cache (inside the container) for this dataset

    Returns:
        None
    """
    logger = LMLogger.get_logger()

    p = os.getpid()
    try:
        logger.info(f"(Job {p}) Starting clean_dataset_file_cache(logged_in_username={logged_in_username},"
                    f"dataset_owner={dataset_owner}, dataset_name={dataset_name}")

        im = InventoryManager()

        # Check for dataset
        try:
            im.load_dataset(logged_in_username, dataset_owner, dataset_name)
            logger.info(f"{logged_in_username}/{dataset_owner}/{dataset_name} still exists. Skipping file cache clean.")
            return
        except InventoryException:
            # Dataset not found, move along
            pass

        # Check for submodule references
        for lb in im.list_labbooks(logged_in_username):
            for ds in im.get_linked_datasets(lb):
                if ds.namespace == dataset_owner and ds.name == dataset_name:
                    logger.info(f"{logged_in_username}/{dataset_owner}/{dataset_name} still referenced by {str(lb)}."
                                f" Skipping file cache clean.")
                    return

        # If you get here the dataset no longer exists and is not used by any projects, clear files
        shutil.rmtree(cache_location)

    except Exception as err:
        logger.error(f"(Job {p}) Error in clean_dataset_file_cache job")
        logger.exception(err)
        raise


def update_environment_repositories() -> None:
    """Method to clone / update the environment repositories

    Returns:
        None
    """
    logger = LMLogger.get_logger()

    lock = RepositoryLock()

    try:
        lock.acquire(failfast=True)
    except:
        logger.warn("Could not acquire repository lock, not updating")
        return

    logger.info("Cloning/Updating environment repositories.")

    try:
        erm = RepositoryManager()
        update_successful = erm.update_repositories()
        if update_successful:
            logger.info("Indexing environment repositories.")
            erm.index_repositories()
            logger.info("Environment repositories updated and ready.")
        else:
            logger.info("Unable to update environment repositories at startup, most likely due to lack of internet access.")
    except Exception as e:
        # If there is an error don't release the lock, as the repositories are
        # not in the expected state
        logger.exception(e)
        logger.critical("Not releasing repository lock, restart API service")
        raise

    lock.release()


def index_labbook_filesystem():
    """To be implemented later. """
    raise NotImplemented


def test_exit_success():
    """Used only for testing -- vacuous method to always succeed and return 0. """
    return 0


def test_exit_fail():
    """Used only for testing -- always throws an exception"""
    raise Exception("Intentional Exception from job `test_exit_fail`")


def test_sleep(n):
    """Used only for testing -- example method with argument. """
    logger = LMLogger.get_logger()
    logger.info("Starting test_sleep({}) in pid {}".format(n, os.getpid()))

    try:
        job = get_current_job()
        job.meta['sample'] = 'test_sleep metadata'
        job.meta['pid'] = int(os.getpid())
        job.save_meta()

        time.sleep(n)
        logger.info("Completed test_sleep in pid {}".format(os.getpid()))
        return 0
    except Exception as e:
        logger.error("Error on test_sleep in pid {}: {}".format(os.getpid(), e))
        raise


def test_incr(path):
    logger = LMLogger.get_logger()
    logger.info("Starting test_incr({}) in pid {}".format(path, os.getpid()))

    try:
        amt = 1
        if not os.path.exists(path):
            logger.info("Creating {}".format(path))
            with open(path, 'w') as fp:
                json.dump({'amt': amt}, fp)
        else:
            logger.info("Loading {}".format(path))
            with open(path, 'r') as fp:
                amt_dict = json.load(fp)
            logger.info("Amt = {}")
            with open(path, 'w') as fp:
                amt_dict['amt'] = amt_dict['amt'] + 1
                json.dump(amt_dict, fp)
            logger.info("Set amt = {} in {}".format(amt_dict['amt'], path))
    except Exception as e:
        logger.error("Error on test_incr in pid {}: {}".format(os.getpid(), e))
        raise
