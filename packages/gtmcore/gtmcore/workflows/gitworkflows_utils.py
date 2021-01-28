import subprocess
import time
import os
import shutil
import uuid
from typing import Any, Optional, Callable, List

from gtmcore.gitlib import RepoLocation
from gtmcore.workflows.gitlab import GitLabManager
from gtmcore.activity import ActivityStore, ActivityType, ActivityRecord, \
                             ActivityDetailType, ActivityDetailRecord, \
                             ActivityAction
from gtmcore.activity.utils import ImmutableList, DetailRecordList, TextData
from gtmcore.exceptions import GigantumException
from gtmcore.labbook import LabBook
from gtmcore.labbook.schemas import migrate_schema_to_current, \
                                    CURRENT_SCHEMA as CURRENT_LABBOOK_SCHEMA
from gtmcore.inventory import Repository
from gtmcore.inventory.inventory import InventoryManager
from gtmcore.logging import LMLogger
from gtmcore.configuration.utils import call_subprocess
from gtmcore.inventory.branching import BranchManager, MergeError
from gtmcore.configuration import Configuration
from gtmcore.dispatcher import Dispatcher
import gtmcore.dispatcher.dataset_jobs


logger = LMLogger.get_logger()


MERGE_CONFLICT_STRING = "Automatic merge failed"


class WorkflowsException(Exception):
    pass


class GitLabRemoteError(WorkflowsException):
    pass


# TODO #1456: Subprocess calls to Git should be consolidated in the internal Git API - currently git_fs_shim.py
def git_garbage_collect(repository: Repository) -> None:
    """Run "git gc" (garbage collect) over the repo. If run frequently enough, this only takes a short time
    even on large repos.

    Note!! This method assumes the subject repository has already been locked!

    Args:
        repository: Subject Repository

    Returns:
        None

    Raises:
        subprocess.CalledProcessError when git gc fails.
        """
    logger.info(f"Running git gc (Garbage Collect) in {str(repository)}...")

    try:
        call_subprocess(['git', 'gc'], cwd=repository.root_dir)
    except subprocess.CalledProcessError:
        logger.warning(f"Ignore `git gc` error - {str(repository)} repo remains unpruned")


def create_remote_gitlab_repo(repository: Repository, username: str, visibility: str,
                              access_token: Optional[str] = None, id_token: Optional[str] = None) -> None:
    """Create a new repository in GitLab,

    Note: It may make more sense to factor this out later on. """
    config = Configuration()
    server_config = config.get_server_configuration()

    if not access_token or not id_token:
        raise ValueError("Creating a remote repository requires a valid session")

    try:
        # Add collaborator to remote service
        mgr = GitLabManager(server_config.git_url,
                            server_config.hub_api_url,
                            access_token=access_token,
                            id_token=id_token)
        mgr.configure_git_credentials(server_config.git_url, username)
        mgr.create_labbook(namespace=InventoryManager().query_owner(repository),
                           labbook_name=repository.name,
                           visibility=visibility)

        # URL construction logic doesn't belong at the level of Git workflows, but it works for now
        remote = RepoLocation(f"{server_config.git_url}{username}/{repository.name}",
                              current_username=username)
        repository.add_remote("origin", remote.remote_location)
    except Exception as e:
        raise GitLabRemoteError(e)


# TODO #1456: Subprocess calls to Git should be consolidated in the internal Git API - currently git_fs_shim.py
def publish_to_remote(repository: Repository, username: str, remote: str,
                      feedback_callback: Callable) -> None:
    # TODO(billvb) - Refactor all (or part) to BranchManager
    bm = BranchManager(repository, username=username)
    if bm.workspace_branch != bm.active_branch:
        raise ValueError(f'Must be on branch {bm.workspace_branch} to publish')

    current_server = repository.client_config.get_server_configuration()
    feedback_callback(f"Preparing to publish {repository.name} to {current_server.name}")
    git_garbage_collect(repository)

    # Try five attempts to fetch - the remote repo could have been created just milliseconds
    # ago, so may need a few moments to settle before it supports all the git operations.
    for tr in range(5):
        try:
            repository.git.fetch(remote=remote)
            break
        except Exception as e:
            logger.warning(f"Fetch attempt {tr+1}/5 failed for {str(repository)}: {e}")
            time.sleep(1)
    else:
        raise ValueError(f"Timed out trying to fetch repo for {str(repository)}")

    feedback_callback(f"Pushing data to {current_server.name}. Please wait...")
    call_git_subprocess(['git', 'push', '--progress', '--set-upstream', 'origin', bm.workspace_branch],
                        cwd=repository.root_dir, feedback_callback=feedback_callback)
    feedback_callback(f"Publish complete.")
    repository.git.clear_checkout_context()


# TODO #1456: Subprocess calls to Git should be consolidated in the internal Git API - currently git_fs_shim.py
def _set_upstream_branch(repository: Repository, branch_name: str, feedback_cb: Callable):
    set_upstream_tokens = ['git', 'push', '--progress', '--set-upstream', 'origin', branch_name]
    call_git_subprocess(set_upstream_tokens, cwd=repository.root_dir, feedback_callback=feedback_cb)


# TODO #1456: Subprocess calls to Git should be consolidated in the internal Git API - currently git_fs_shim.py
def _pull(repository: Repository, branch_name: str, override: str, feedback_cb: Callable,
          username: Optional[str] = None) -> None:
    current_server = repository.client_config.get_server_configuration()
    feedback_cb(f"Pulling latest changes from {current_server.name}. Please wait...")

    cp = repository.git.commit_hash

    # Run a pull and if you get output, a conflict occurred
    output = call_git_subprocess(f'git pull --progress'.split(),
                                 cwd=repository.root_dir,
                                 feedback_callback=feedback_cb)
    if output:
        feedback_cb(f"Detected merge conflict, resolution method = {override}")
        bm = BranchManager(repository, username='')
        conflicted_files = bm._infer_conflicted_files(output)
        if 'abort' == override:
            conflicted_str = "\n".join(conflicted_files)
            feedback_cb(f'Sync aborted due to conflicts while pulling changes from the server.'
                        f'The following files conflicted:\n\n {conflicted_str}')
            call_subprocess(f'git reset --hard {cp}'.split(), cwd=repository.root_dir)
            raise MergeError(f'Sync aborted due to conflicts while pulling changes from {current_server.name}')

        # Resolving conflict on pull
        call_subprocess(f'git checkout --{override} {" ".join(conflicted_files)}'.split(),
                        cwd=repository.root_dir)
        call_subprocess('git add .'.split(), cwd=repository.root_dir)
        call_subprocess('git commit -m "Merge"'.split(), cwd=repository.root_dir)
        feedback_cb("Resolved merge conflict")


def sync_branch(repository: Repository, username: Optional[str], override: str,
                pull_only: bool, feedback_callback: Callable) -> int:
    """"""
    if not repository.has_remote:
        return 0

    repository.sweep_uncommitted_changes()

    current_server = repository.client_config.get_server_configuration()
    feedback_callback(f"Preparing to sync {repository.name} with {current_server.name}.")
    repository.git.fetch()

    bm = BranchManager(repository)
    branch_name = bm.active_branch

    if pull_only and branch_name not in bm.branches_remote:
        # Cannot pull when remote branch doesn't exist.
        feedback_callback("Pull complete - nothing to pull")
        repository.git.clear_checkout_context()
        return 0

    if branch_name not in bm.branches_remote:
        # Branch does not exist, so push it to remote.
        feedback_callback(f"Pushing current branch \"{branch_name}\" to {current_server.name}. Please wait...")
        _set_upstream_branch(repository, bm.active_branch, feedback_callback)
        repository.git.clear_checkout_context()
        feedback_callback("Sync complete")
        return 0
    else:
        pulled_updates_count = bm.get_commits_behind()
        _pull(repository, branch_name, override, feedback_callback, username=username)
        should_push = not pull_only
        if should_push:
            feedback_callback(f"Pushing changes in current branch \"{branch_name}\" to {current_server.name}. "
                              f"Please wait...")
            # Skip pushing back up if set to pull_only
            push_tokens = f'git push --progress origin {branch_name}'.split()
            if branch_name not in bm.branches_remote:
                push_tokens.insert(2, "--set-upstream")
            call_git_subprocess(push_tokens, cwd=repository.root_dir, feedback_callback=feedback_callback)
            feedback_callback("Sync complete")
        else:
            feedback_callback("Pull complete")

        repository.git.clear_checkout_context()
        return pulled_updates_count


# TODO #1456: Subprocess calls to Git should be consolidated in the internal Git API - currently git_fs_shim.py
def migrate_labbook_schema(labbook: LabBook) -> None:
    # Fallback point in case of a problem
    initial_commit = labbook.git.commit_hash

    try:
        migrate_schema_to_current(labbook.root_dir)
    except Exception as e:
        logger.exception(e)
        call_subprocess(f'git reset --hard {initial_commit}'.split(), cwd=labbook.root_dir)
        raise

    msg = f"Migrate schema to {CURRENT_LABBOOK_SCHEMA}"
    labbook.git.add(labbook.config_path)
    cmt = labbook.git.commit(msg, author=labbook.author, committer=labbook.author)
    adr = ActivityDetailRecord(ActivityDetailType.LABBOOK,
                               show=True,
                               importance=100,
                               action=ActivityAction.EDIT,
                               data=TextData('plain', msg))

    ar = ActivityRecord(ActivityType.LABBOOK,
                        message=msg,
                        show=True,
                        importance=255,
                        linked_commit=cmt.hexsha,
                        detail_objects=DetailRecordList([adr]),
                        tags=ImmutableList(['schema', 'update', 'migration']))

    ars = ActivityStore(labbook)
    ars.create_activity_record(ar)


# TODO #1456: Subprocess calls to Git should be consolidated in the internal Git API - currently git_fs_shim.py
def migrate_labbook_branches(labbook: LabBook) -> None:
    bm = BranchManager(labbook)
    if 'gm.workspace' not in bm.active_branch:
        raise ValueError('Can only migrate branches if active branch contains'
                         '"gm.workspace"')

    master_branch = 'master'
    if master_branch in bm.branches_local:
        bm.remove_branch(master_branch)

    bm.create_branch(master_branch)


# TODO #1456: Subprocess calls to Git should be consolidated in the internal Git API - currently git_fs_shim.py
def _clone(remote_url: str, working_dir: str) -> str:

    clone_tokens = f"git clone --progress {remote_url}".split()
    call_subprocess(clone_tokens, cwd=working_dir)

    # Affirm there is only one directory created
    dirs = os.listdir(working_dir)
    if len(dirs) != 1:
        raise GigantumException('Git clone produced extra directories')

    p = os.path.join(working_dir, dirs[0])
    if not os.path.exists(p):
        raise GigantumException('Could not find expected path of repo after clone')

    try:
        # This is for backward compatibility -- old projects will clone to
        # branch "gm.workspace" by default -- even if it has already been migrated.
        # This will therefore set the user to the proper branch if the project has been
        # migrated, and will have no affect if it hasn't
        r = call_subprocess("git checkout master".split(), cwd=p)
    except Exception as e:
        logger.error(e)

    return p


# TODO #1456: Subprocess calls to Git should be consolidated in the internal Git API - currently git_fs_shim.py
def clone_repo(remote_url: str, username: str, owner: str,
               load_repository: Callable[[str], Any],
               put_repository: Callable[[str, str, str], Any],
               make_owner: bool = False) -> Repository:

    # Clone into a temporary directory, such that if anything
    # gets messed up, then this directory will be cleaned up.
    tempdir = os.path.join(Configuration().upload_dir, f"{username}_{owner}_clone_{uuid.uuid4().hex[0:10]}")
    os.makedirs(tempdir)
    path = _clone(remote_url=remote_url, working_dir=tempdir)
    candidate_repo = load_repository(path)

    if os.environ.get('WINDOWS_HOST'):
        logger.warning("Imported on Windows host - set fileMode to false")
        call_subprocess("git config core.fileMode false".split(),
                        cwd=candidate_repo.root_dir)

    repository = put_repository(candidate_repo.root_dir, username, owner)
    shutil.rmtree(tempdir)

    return repository


def process_linked_datasets(labbook: LabBook, logged_in_username: str) -> None:
    """Method to update or init any linked dataset submodule references, clean up lingering files, and schedule
    jobs to auto-import if needed

    Args:
        labbook: the labbook to analyze
        logged_in_username: the current logged in username

    Returns:

    """
    im = InventoryManager()

    # Update linked datasets inside the Project or clean them out if needed
    im.update_linked_datasets(labbook, logged_in_username)

    # Check for linked datasets, and schedule auto-imports
    d = Dispatcher()
    datasets = im.get_linked_datasets(labbook)
    for ds in datasets:
        kwargs = {
            'logged_in_username': logged_in_username,
            'dataset_owner': ds.namespace,
            'dataset_name': ds.name,
            'remote_url': ds.remote,
        }
        metadata = {'dataset': f"{logged_in_username}|{ds.namespace}|{ds.name}",
                    'method': 'dataset_jobs.check_and_import_dataset'}

        d.dispatch_task(gtmcore.dispatcher.dataset_jobs.check_and_import_dataset,
                        kwargs=kwargs,
                        metadata=metadata)


# TODO #1456: Subprocess calls to Git should be consolidated in the internal Git API - currently git_fs_shim.py
def call_git_subprocess(cmd_tokens: List[str], cwd: str, feedback_callback: Callable) -> Optional[str]:
    """Execute a subprocess call to git from a background job

    Args:
        cmd_tokens: List of command tokens, e.g., ['ls', '-la']
        cwd: Current working directory
        feedback_callback: callback to print to UI

    Returns:
        Decoded stdout of called process after completing IF merge conflicts occurred

    Raises:
        subprocess.CalledProcessError
    """
    output = ""
    with subprocess.Popen(cmd_tokens, cwd=cwd, shell=False,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True) as sp:
        for line in sp.stdout:  # type: ignore
            # Send each line to the feedback callback when it is available and also append
            # to the complete output (needed when a conflict occurs)
            feedback_callback(line)
            output = f"{output}{line}"

    if sp.returncode != 0:
        if MERGE_CONFLICT_STRING in line:
            # This is a merge conflict that we need to handle differently.
            # Currently, the above string MERGE_CONFLICT_STRING is used to detect when
            # a merge conflict has occurred.
            #
            # When you do get a merge conflict, send the whole output back to the caller
            # so the output can be processed to find the conflicted files.
            return output
        else:
            # An error occurred
            cmd = " ".join(cmd_tokens)
            raise Exception(f"An error occurred while running `{cmd}`")
    else:
        # No error. Don't return output.
        return None


def handle_git_feedback(current_feedback: str, message: str) -> str:
    """Function to handle git output in a reasonable way for UI rendering for the user

    Args:
        current_feedback: current string of feedback stored in the background job
        message: new message output from git

    Returns:
        string containing all messages separated by newlines
    """
    # We manage whitespace for git feedback in this function
    message = message.strip()

    # Clean up some of the output that we know we want to ignore for now
    # that isn't super useful to sent back to the user.
    lines_to_skip = (".git/info/lfs.locksverify true",
                     "Locking support detected on remote",
                     "hint:")
    if message.startswith(lines_to_skip):
        return current_feedback

    if not current_feedback:
        # This is the first line provided as feedback so return the message.
        return message

    # Check if the new message is actually an update to the previous message (e.g. a progress indicator)
    lines = current_feedback.split('\n')
    last_line = lines[-1]
    msg_parts = message.split(':')
    if len(msg_parts) > 1:
        # You might have a progress update vs. a new message
        last_line_parts = last_line.split(':')
        if len(msg_parts) == len(last_line_parts):
            if msg_parts[0] == last_line_parts[0]:
                # It's an update! Remove last line to update instead of just append
                _ = lines.pop()

    lines.append(message)
    return "\n".join(lines)
