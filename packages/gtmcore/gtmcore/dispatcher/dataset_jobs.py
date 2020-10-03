import asyncio
import copy
import os
import shutil
import time
from typing import Optional, List, Tuple, Union

from humanfriendly import format_size
from rq import get_current_job

from gtmcore.configuration import Configuration
from gtmcore.dataset import Manifest
from gtmcore.dataset.manifest.job import generate_bg_hash_job_list
from gtmcore.dataset.manifest.manifest import StatusResult
from gtmcore.dataset.storage import GigantumObjectStore, LocalFilesystemBackend
from gtmcore.dataset.storage.s3 import PublicS3Bucket
from gtmcore.dispatcher import Dispatcher
from gtmcore.dispatcher.jobs import update_feedback
from gtmcore.exceptions import GigantumException
from gtmcore.gitlib import GitAuthor, RepoLocation
from gtmcore.inventory.inventory import InventoryManager, InventoryException
from gtmcore.logging import LMLogger
from gtmcore.workflows import gitworkflows_utils, ZipExporter
from gtmcore.workflows.gitlab import GitLabManager
from gtmcore.dataset.io.manager import IOManager
from gtmcore.dataset.io.job import BackgroundDownloadJob
from gtmcore.dataset.io import PushObject


def hash_dataset_files(logged_in_username: str, dataset_owner: str, dataset_name: str,
                       file_list: List) -> None:
    """

    Args:
        logged_in_username: username for the currently logged in user
        dataset_owner: Owner of the labbook if this dataset is linked
        dataset_name: Name of the labbook if this dataset is linked
        file_list: List of files to be hashed

    Returns:
        None
    """
    logger = LMLogger.get_logger()

    p = os.getpid()
    try:
        logger.info(f"(Job {p}) Starting hash_dataset_files(logged_in_username={logged_in_username},"
                    f"dataset_owner={dataset_owner}, dataset_name={dataset_name}")

        ds = load_dataset(logged_in_username, dataset_owner, dataset_name)
        manifest = Manifest(ds, logged_in_username)

        loop = asyncio.get_event_loop()
        hash_task = loop.create_task(manifest.hash_files(file_list))
        loop.run_until_complete(hash_task)
        hash_result, fast_hash_result = hash_task.result()

        job = get_current_job()
        if job:
            job.meta['hash_result'] = ",".join(['None' if v is None else v for v in hash_result])
            job.meta['fast_hash_result'] = ",".join(['None' if v is None else v for v in fast_hash_result])
            job.save_meta()

    except Exception as err:
        logger.error(f"(Job {p}) Error in clean_dataset_file_cache job")
        logger.exception(err)
        raise


def complete_dataset_upload_transaction(logged_in_username: str, logged_in_email: str,
                                        dataset_owner: str, dataset_name: str, dispatcher) -> None:
    """Method to import a dataset from a zip file

    Args:
        logged_in_username: username for the currently logged in user
        logged_in_email: email for the currently logged in user
        dataset_owner: Owner of the labbook if this dataset is linked
        dataset_name: Name of the labbook if this dataset is linked
        dispatcher: Reference to the dispatcher CLASS

    Returns:
        None
    """
    logger = LMLogger.get_logger()
    dispatcher_obj = dispatcher()

    def schedule_bg_hash_job():
        """Method to check if a bg job should get scheduled and do so"""
        num_cores = manifest.get_num_hashing_cpus()
        if sum([x.is_running for x in job_list]) < num_cores:
            for j in job_list:
                if j.is_failed is True and j.failure_count < 3:
                    # Re-schedule failed job
                    job_kwargs['file_list'] = j.file_list
                    job_key = dispatcher_obj.dispatch_task(hash_dataset_files,
                                                           kwargs=job_kwargs,
                                                           metadata=job_metadata)
                    j.job_key = job_key
                    update_feedback(f"Restarted failed file hashing job. Re-processing"
                                    f" {format_size(j.total_bytes)}...")
                    logger.info(f"(Job {p}) Restarted file hash job for"
                                f" {logged_in_username}/{dataset_owner}/{dataset_name}")
                    break

                if j.is_complete is False and j.is_running is False:
                    # Schedule new job
                    job_kwargs['file_list'] = j.file_list
                    job_key = dispatcher_obj.dispatch_task(hash_dataset_files,
                                                           kwargs=job_kwargs,
                                                           metadata=job_metadata)
                    j.job_key = job_key
                    logger.info(f"(Job {p}) Scheduled file hash job for"
                                f" {logged_in_username}/{dataset_owner}/{dataset_name}")
                    break

    p = os.getpid()
    try:
        logger.info(f"(Job {p}) Starting complete_dataset_upload_transaction(logged_in_username={logged_in_username},"
                    f"dataset_owner={dataset_owner}, dataset_name={dataset_name}")

        author = GitAuthor(name=logged_in_username, email=logged_in_email)
        dispatcher_obj = Dispatcher()
        ds = InventoryManager().load_dataset(logged_in_username, dataset_owner, dataset_name, author=author)
        manifest = Manifest(ds, logged_in_username)

        with ds.lock():
            # Detect changes
            status = manifest.status()

            # Collect filenames that need to be hashed
            filenames = copy.deepcopy(status.modified)
            filenames.extend(status.created)

            # If there are new/updated files, spread work across cores while providing reasonable feedback
            if filenames:
                job_list = generate_bg_hash_job_list(filenames, manifest, dispatcher_obj)
                total_bytes = sum([x.total_bytes for x in job_list])

                job_kwargs = {
                    'logged_in_username': logged_in_username,
                    'dataset_owner': dataset_owner,
                    'dataset_name': dataset_name,
                    'file_list': list(),
                }
                job_metadata = {'dataset': f"{logged_in_username}|{dataset_owner}|{dataset_name}",
                                'method': 'hash_dataset_files'}

                update_feedback(f"Please wait while file contents are analyzed. "
                                f"Processing {format_size(total_bytes)}...", has_failures=False)
                logger.info(f"(Job {p}) Starting file hash processing for"
                            f" {logged_in_username}/{dataset_owner}/{dataset_name} with {len(job_list)} jobs")

                while True:
                    # Check if you need to schedule jobs and schedule up to 1 job per iteration
                    schedule_bg_hash_job()

                    # Refresh all job statuses and update status feedback
                    completed_job_status = [x.refresh_status() for x in job_list]
                    completed_bytes = sum([s.total_bytes for s, c in zip(job_list, completed_job_status) if c is True])
                    update_feedback(f"Please wait while file contents are analyzed. "
                                    f"{format_size(completed_bytes)} of {format_size(total_bytes)} complete...",
                                    percent_complete=(float(completed_bytes)/float(total_bytes)) * 100)

                    # Check if you are done
                    completed_or_failed = sum([(x.is_complete or (x.failure_count >= 3)) for x in job_list])
                    if completed_or_failed == len(job_list):
                        break

                    # Update once per second
                    time.sleep(1)

                # Manually complete update process for updated/created files
                failed_files = list()
                for job in job_list:
                    if job.is_complete:
                        for f, h, fh in zip(job.file_list, job.get_hash_result(), job.get_fast_hash_result()):
                            if not fh or not h:
                                failed_files.append(f)
                                continue

                            _, file_bytes, mtime = fh.split("||")
                            manifest._manifest_io.add_or_update(f, h, mtime, file_bytes)
                    else:
                        failed_files.extend(job.file_list)

                # Message for hard failures
                if failed_files:
                    detail_msg = f"The following files failed to hash. Try re-uploading the files again:\n"
                    detail_file_list = " \n".join(failed_files)
                    detail_msg = f"{detail_msg}{detail_file_list}"
                    update_feedback(f"An error occurred while processing some files. Check details and re-upload.",
                                    has_failures=True, failure_detail=detail_msg)

            if status.deleted:
                manifest.delete_fast_hashes(status.deleted)
                for relative_path in status.deleted:
                    manifest._manifest_io.remove(relative_path)

            manifest._manifest_io.persist()

            # Complete sweep operation
            manifest.sweep_all_changes(status=status, upload=True)

    except Exception as err:
        logger.error(f"(Job {p}) Error in clean_dataset_file_cache job")
        logger.exception(err)
        raise


def check_and_import_dataset(logged_in_username: str, dataset_owner: str, dataset_name: str, remote_url: str,
                             access_token: Optional[str] = None, id_token: Optional[str] = None) -> None:
    """Job to check if a dataset exists in the user's working directory, and if not import it. This is primarily used
    when importing, syncing, or switching branches on a project with linked datasets

    Args:
        logged_in_username: username for the currently logged in user
        dataset_owner: Owner of the labbook if this dataset is linked
        dataset_name: Name of the labbook if this dataset is linked
        remote_url: URL of the dataset to import if needed
        access_token: The current user's access token, needed to initialize git credentials in certain situations
        id_token: The current user's id token, needed to initialize git credentials in certain situations

    Returns:
        None
    """
    logger = LMLogger.get_logger()
    p = os.getpid()
    logger.info(f"(Job {p}) Starting check_and_import_dataset(logged_in_username={logged_in_username},"
                f"dataset_owner={dataset_owner}, dataset_name={dataset_name}")

    remote = RepoLocation(remote_url, logged_in_username)
    try:
        im = InventoryManager()

        try:
            # Check for dataset already existing in the user's working directory
            im.load_dataset(logged_in_username, dataset_owner, dataset_name)
            logger.info(f"{logged_in_username}/{dataset_owner}/{dataset_name} exists. Skipping auto-import.")
            return
        except InventoryException:
            # Dataset not found, import it
            logger.info(f"{logged_in_username}/{dataset_owner}/{dataset_name} not found. "
                        f"Auto-importing remote dataset from {remote_url}")
            config_obj = Configuration()
            server_config = config_obj.get_server_configuration()

            # TODO gigantum/ideas#11: this token logic is NOT duplicated in the standard dataset or labbook flows. It
            #  could be handled in gitworkflows_utils.clone_repo below, or somewhere in a git auth logic module/object.
            #  Note that some complexity derives from the fact that we don't have access to the Flask session here.
            if access_token:
                if not id_token:
                    raise ValueError("Access and ID tokens are required to initialize git credentials")

                # If the access token is set, git creds should be configured
                gl_mgr = GitLabManager(remote.host, hub_api=server_config.hub_api_url,
                                       access_token=access_token, id_token=id_token)
                gl_mgr.configure_git_credentials(remote.host, logged_in_username)

            gitworkflows_utils.clone_repo(remote_url=remote.remote_location, username=logged_in_username,
                                          owner=dataset_owner,
                                          load_repository=im.load_dataset_from_directory,
                                          put_repository=im.put_dataset)
            logger.info(f"{logged_in_username}/{dataset_owner}/{dataset_name} auto-imported successfully")

    except Exception as err:
        logger.error(f"(Job {p}) Error in check_and_import_dataset job")
        logger.exception(err)
        raise


def push_dataset_objects(objs: List[PushObject], logged_in_username: str, dataset_owner: str, dataset_name: str,
                         access_token: str, id_token: str) -> None:
    """Method to push a collection of objects from a dataset's backend

    Note that we currently only intend to support pushing to GigantumHub

    Args:
        objs: List if file PushObject to push
        logged_in_username: username for the currently logged in user
        dataset_owner: Owner of the dataset containing the files to download
        dataset_name: Name of the dataset containing the files to download
        access_token: Gigantum API access token
        id_token: Gigantum API ID token

    Returns:
        str: directory path of imported labbook
    """
    logger = LMLogger.get_logger()

    try:
        p = os.getpid()
        logger.info(f"(Job {p}) Starting push_dataset_objects(logged_in_username={logged_in_username},"
                    f"dataset_owner={dataset_owner}, dataset_name={dataset_name}")

        ds = load_dataset(logged_in_username, dataset_owner, dataset_name)

        ds.namespace = dataset_owner
        backend = ds.backend
        if not isinstance(backend, GigantumObjectStore):
            raise GigantumException(f'Can only push objects for Gigantum Datasets! (not {type(ds).__name__})')

        ds.backend.credentials = {
            'access_token': access_token,
            'id_token': id_token,
        }

        m = Manifest(ds, logged_in_username)
        iom = IOManager(ds, m)

        result = iom.push_objects(objs, progress_update_fn=progress_update_callback)

        job = get_current_job()
        if job:
            job.meta['failures'] = ",".join([f"{x.object_path}|{x.dataset_path}|{x.revision}" for x in result.failure])
            job.meta['message'] = result.message
            job.save_meta()

    except Exception as err:
        logger.exception(err)
        raise


def pull_objects(keys: List[str], logged_in_username: str, access_token: str, id_token: str,
                 dataset_owner: str, dataset_name: str, labbook_owner: Optional[str] = None, labbook_name: Optional[str] = None) -> None:
    """Method to pull a collection of objects from a dataset's backend.

    This runs the IOManager.pull_objects() method with `link_revision=False`. This is because this job can be run in
    parallel multiple times with different sets of keys. You don't want to link until the very end, which is handled
    in the `download_dataset_files` job, which is what scheduled this job.

    Args:
        keys: List if file keys to download
        logged_in_username: username for the currently logged in user
        access_token: Gigantum API access token
        id_token: Gigantum API ID token
        dataset_owner: Owner of the dataset containing the files to download
        dataset_name: Name of the dataset containing the files to download
        labbook_owner: Owner of the labbook if this dataset is linked
        labbook_name: Name of the labbook if this dataset is linked

    Returns:
        str: directory path of imported labbook
    """
    logger = LMLogger.get_logger()

    try:
        p = os.getpid()
        logger.info(f"(Job {p}) Starting pull_objects(logged_in_username={logged_in_username},"
                    f"dataset_owner={dataset_owner}, dataset_name={dataset_name}, labbook_owner={labbook_owner},"
                    f" labbook_name={labbook_name}")

        ds = load_dataset(logged_in_username, dataset_owner, dataset_name,
                          labbook_owner, labbook_name)

        backend = ds.backend
        if not isinstance(backend, GigantumObjectStore):
            raise GigantumException("pull_objects only supported for GigantumObjectStore")

        backend.credentials = {
            'access_token': access_token,
            'id_token': id_token,
        }

        m = Manifest(ds, logged_in_username)

        iom = IOManager(ds, m)

        result = iom.pull_objects(keys=keys, progress_update_fn=progress_update_callback, link_revision=False)

        job = get_current_job()
        if job:
            job.meta['failure_keys'] = ",".join([x.dataset_path for x in result.failure])
            job.meta['message'] = result.message
            job.save_meta()

    except Exception as err:
        logger.exception(err)
        raise


def download_dataset_files(logged_in_username: str,
                           access_token: str, id_token: str,
                           dataset_owner: str, dataset_name: str,
                           labbook_owner: Optional[str] = None, labbook_name: Optional[str] = None,
                           all_keys: Optional[bool] = False, keys: Optional[List[str]] = None) -> None:
    """Method to download files from a dataset in the background and provide status to the UI.

    This job schedules `pull_objects` jobs after splitting up the download work into batches. At the end, the job
    removes any partially downloaded files (due to failures) and links all the files for the dataset.

    Args:
        logged_in_username: username for the currently logged in user
        access_token: Gigantum API access token
        id_token: Gigantum API ID token
        dataset_owner: Owner of the dataset containing the files to download
        dataset_name: Name of the dataset containing the files to download
        labbook_owner: Owner of the labbook if this dataset is linked
        labbook_name: Name of the labbook if this dataset is linked
        all_keys: Boolean indicating if all remaining files should be downloaded
        keys: List if file keys to download

    Returns:
        str: directory path of imported labbook
    """
    dispatcher_obj = Dispatcher()

    logger = LMLogger.get_logger()

    try:
        p = os.getpid()
        logger.info(f"(Job {p}) Starting download_dataset_files(logged_in_username={logged_in_username},"
                    f" dataset_owner={dataset_owner}, dataset_name={dataset_name}, labbook_owner={labbook_owner},"
                    f" labbook_name={labbook_name}, all_keys={all_keys}, keys={keys}")

        ds = load_dataset(logged_in_username, dataset_owner, dataset_name, labbook_owner, labbook_name)

        backend = ds.backend
        if not isinstance(backend, GigantumObjectStore):
            raise GigantumException("pull_objects only supported for GigantumObjectStore")

        backend.credentials = {
            'access_token': access_token,
            'id_token': id_token,
        }

        m = Manifest(ds, logged_in_username)
        iom = IOManager(ds, m)

        key_batches, total_bytes, num_files = iom.compute_pull_batches(keys, pull_all=all_keys)

        failure_keys = list()
        if key_batches:
            # Schedule jobs for batches
            bg_jobs = list()
            for keys in key_batches:
                job_kwargs = {
                    'keys': keys,
                    'logged_in_username': logged_in_username,
                    'access_token': access_token,
                    'id_token': id_token,
                    'dataset_owner': dataset_owner,
                    'dataset_name': dataset_name,
                    'labbook_owner': labbook_owner,
                    'labbook_name': labbook_name
                }
                job_metadata = {'dataset': f"{logged_in_username}|{dataset_owner}|{dataset_name}",
                                'method': 'pull_objects'}

                job_key = dispatcher_obj.dispatch_task(method_reference=pull_objects,
                                                       kwargs=job_kwargs,
                                                       metadata=job_metadata,
                                                       persist=True)
                bg_jobs.append(BackgroundDownloadJob(dispatcher_obj, keys, job_key))

            update_feedback(f"Please wait - Downloading {num_files} files ({format_size(total_bytes)}) - 0% complete",
                            percent_complete=0,
                            has_failures=False)
            logger.info(f"(Job {p}) Starting file downloads for"
                        f" {logged_in_username}/{dataset_owner}/{dataset_name} with {len(key_batches)} jobs")

            while sum([(x.is_complete or x.is_failed) for x in bg_jobs]) != len(bg_jobs):
                # Refresh all job statuses and update status feedback
                [j.refresh_status() for j in bg_jobs]
                total_completed_bytes = sum([j.completed_bytes for j in bg_jobs])
                pc = (float(total_completed_bytes) / float(total_bytes)) * 100
                update_feedback(f"Please wait - Downloading {num_files} files ({format_size(total_completed_bytes)} of "
                                f"{format_size(total_bytes)}) - {round(pc)}% complete",
                                percent_complete=pc)
                time.sleep(1)

            # Aggregate failures if they exist
            for j in bg_jobs:
                if j.is_failed:
                    # Whole job failed...assume entire batch should get re-uploaded for now
                    failure_keys.extend(j.keys)
                else:
                    failure_keys.extend(j.get_failed_keys())

        # Set final status for UI
        if len(failure_keys) == 0:
            update_feedback(f"Download complete!", percent_complete=100, has_failures=False)
        else:
            failure_str = ""
            for f in failure_keys:
                # If any failed files partially downloaded, remove them.
                abs_dataset_path = os.path.join(m.current_revision_dir, f)
                path_hash = m.hash_for_path(f)
                abs_object_path = ds.backend.hash_to_object_path(path_hash)
                if os.path.exists(abs_dataset_path):
                    os.remove(abs_dataset_path)
                if os.path.exists(abs_object_path):
                    os.remove(abs_object_path)
                failure_str = f"{failure_str}{f}\n"

            failure_detail_str = f"Files that failed to download:\n{failure_str}"
            update_feedback("", has_failures=True, failure_detail=failure_detail_str)

        # Link dataset files, so anything that was successfully pulled will materialize
        m.link_revision()

        if len(failure_keys) > 0:
            # If any downloads failed, exit non-zero to the UI knows there was an error
            raise IOError(f"{len(failure_keys)} file(s) failed to download. Check message detail and try again.")

    except Exception as err:
        logger.exception(err)
        raise


def verify_dataset_contents(logged_in_username: str, dataset_owner: str, dataset_name: str,
                            labbook_owner: Optional[str] = None, labbook_name: Optional[str] = None) -> None:
    """Method to update/populate an unmanaged dataset from it local state

    Args:
        logged_in_username: username for the currently logged in user
        dataset_owner: Owner of the dataset containing the files to download
        dataset_name: Name of the dataset containing the files to download
        labbook_owner: Owner of the labbook if this dataset is linked
        labbook_name: Name of the labbook if this dataset is linked

    Returns:
        None
    """
    logger = LMLogger.get_logger()

    try:
        p = os.getpid()
        logger.info(f"(Job {p}) Starting verify_dataset_contents(logged_in_username={logged_in_username},"
                    f"dataset_owner={dataset_owner}, dataset_name={dataset_name},"
                    f"labbook_owner={labbook_owner}, labbook_name={labbook_name}")

        ds = load_dataset(logged_in_username, dataset_owner, dataset_name, labbook_owner, labbook_name)

        result = ds.backend.verify_contents(ds, update_meta)
        update_modified_keys(result)

    except Exception as err:
        logger.exception(err)
        raise


def update_local_dataset(logged_in_username: str, dataset_owner: str, dataset_name: str) -> None:
    """Method to update/populate a local dataset from its local state

    Args:
        logged_in_username: username for the currently logged in user
        dataset_owner: Owner of the dataset
        dataset_name: Name of the dataset

    Returns:

    """
    logger = LMLogger.get_logger()

    try:
        p = os.getpid()
        logger.info(f"(Job {p}) Starting update_local_dataset(logged_in_username={logged_in_username},"
                    f"dataset_owner={dataset_owner}, dataset_name={dataset_name}")

        im = InventoryManager()
        ds = im.load_dataset(logged_in_username, dataset_owner, dataset_name)
        ds.namespace = dataset_owner

        backend = ds.backend
        if not isinstance(backend, LocalFilesystemBackend):
            raise ValueError("Can only auto-update unmanaged dataset types")

        # XXX moved/modified from local backend.update_from_local()

        m = Manifest(ds, logged_in_username)

        update_meta("Updating Dataset manifest from local file state.")

        status_result = m.status()

        if (status_result is not None) and (status_result.modified is not None):
            modified_keys = copy.deepcopy(status_result.modified)
        else:
            modified_keys = list()

        # if verify_contents:
        #     modified_keys.extend(backend.verify_contents(ds, update_meta))

        # Create StatusResult to force modifications
        if status_result:
            created_result = copy.deepcopy(status_result.created)
            # Check if any directories got created
            for key in status_result.created:
                if key[-1] != '/':
                    # a file
                    if os.path.dirname(key) not in m.manifest:
                        # Add the directory to the manifest
                        created_result.append(f"{os.path.dirname(key)}/")

            created_result = list(set(created_result))
            if '/' in created_result:
                created_result.remove('/')

            # Combine a previous StatusResult object (typically from "update_from_remote")
            status = StatusResult(created=created_result,
                                  modified=modified_keys,
                                  deleted=status_result.deleted)
        else:
            status = StatusResult(created=[], modified=modified_keys, deleted=[])

        # Update the manifest
        m.update(status)
        m.create_update_activity_record(status)

        # Link the revision dir
        m.link_revision()

        update_meta("Update complete.")

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


def import_dataset_from_zip(archive_path: str, username: str, owner: str) -> str:
    """Method to import a dataset from a zip file

    Args:
        archive_path: Path to the uploaded zip
        username: Username
        owner: Owner username

    Returns:
        str: directory path of imported labbook
    """
    p = os.getpid()
    logger = LMLogger.get_logger()
    logger.info(f"(Job {p}) Starting import_dataset_from_zip(archive_path={archive_path},"
                f"username={username}, owner={owner}")

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


def update_unmanaged_dataset_from_remote(logged_in_username: str, access_token: str, id_token: str,
                                         dataset_owner: str, dataset_name: str) -> None:
    """Method to update/populate an unmanaged dataset from its remote automatically

    Currently hard-coded to the "Public" S3 bucket

    Args:
        logged_in_username: username for the currently logged in user
        access_token: bearer token
        id_token: identity token
        dataset_owner: Owner of the dataset containing the files to download
        dataset_name: Name of the dataset containing the files to download

    Returns:

    """
    logger = LMLogger.get_logger()

    try:
        p = os.getpid()
        logger.info(f"(Job {p}) Starting update_unmanaged_dataset_from_remote(logged_in_username={logged_in_username},"
                    f"dataset_owner={dataset_owner}, dataset_name={dataset_name}")

        im = InventoryManager()
        ds = im.load_dataset(logged_in_username, dataset_owner, dataset_name)

        ds.namespace = dataset_owner
        backend = ds.backend

        # Make more general once we have more external backends
        if not isinstance(backend, PublicS3Bucket):
            raise ValueError("Can only auto-update externally-hosted remote dataset types")

        # Note - if we know the region, we don't need credentials AND you can query for the region of a bucket
        backend.credentials = {'access_token': access_token,
                               'id_token': id_token}

        backend.update_from_remote(ds, update_meta)

    except Exception as err:
        logger.exception(err)
        raise


## Utility functions

def load_dataset(logged_in_username: str, dataset_owner: str, dataset_name: str,
                 labbook_owner: Optional[str] = None, labbook_name: Optional[str] = None):
    """Load a dataset in a variety of contexts

    Args:
        logged_in_username: user
        dataset_owner: gigantum namespace for dataset
        dataset_name: label for dataset
        labbook_owner: gigantum namespace for a project containing the dataset - if specified, dataset will be loaded
          from within the Project, otherwise will be loaded as a top-level dataset
        labbook_name: label for project - required along with labbook_owner to specify the containing project
        check_isinstance: will be passed directly to `isinstance()` builtin after loading the dataset
    """
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

    return ds


def update_meta(msg: str):
    """Method to update the job's text feedback metadata for the UI"""
    job = get_current_job()
    if not job:
        return
    if 'feedback' not in job.meta:
        job.meta['feedback'] = msg
    else:
        job.meta['feedback'] = job.meta['feedback'] + f'\n{msg}'
    job.save_meta()


def update_modified_keys(result):
    """A mildly over-engineered simple function to keep our API consistent"""
    job = get_current_job()
    job.meta['modified_keys'] = result
    job.save_meta()


def progress_update_callback(completed_bytes: int) -> None:
    """Method to update the job's progress metadata and provide feedback to the UI"""
    current_job = get_current_job()
    if not current_job:
        return
    if 'completed_bytes' not in current_job.meta:
        current_job.meta['completed_bytes'] = 0

    current_job.meta['completed_bytes'] = int(current_job.meta['completed_bytes']) + completed_bytes
    current_job.save_meta()
