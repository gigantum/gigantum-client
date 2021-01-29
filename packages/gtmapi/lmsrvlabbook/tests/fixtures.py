from typing import Tuple
import pytest
import tempfile
import os
import uuid
import shutil
import graphene
from flask import Flask
import flask
import time
import redis
import responses
from graphene.test import Client
from gtmcore.files import FileOperations

from gtmcore.container.local_container import get_docker_client
from gtmcore.environment import RepositoryManager
from gtmcore.configuration.configuration import Configuration, deep_update
from gtmcore.auth.identity import get_identity_manager_class
from gtmcore.environment.bundledapp import BundledAppManager

from gtmcore.inventory.inventory import InventoryManager
from lmsrvcore.middleware import DataloaderMiddleware, error_middleware, RepositoryCacheMiddleware
from lmsrvcore.caching import DatasetCacheController
from lmsrvcore.tests.fixtures import insert_cached_identity

from gtmcore.fixtures import (ENV_UNIT_TEST_REPO, ENV_UNIT_TEST_REV, ENV_UNIT_TEST_BASE)
from gtmcore.container import container_for_context
from gtmcore.environment import ComponentManager
from gtmcore.imagebuilder import ImageBuilder

from lmsrvlabbook.api.query import LabbookQuery
from lmsrvlabbook.api.mutation import LabbookMutations

from gtmcore.fixtures.datasets import helper_append_file
from gtmcore.fixtures.fixtures import _create_temp_work_dir
from gtmcore.dataset.cache import get_cache_manager_class
from gtmcore.dataset import Manifest
import gtmcore


@pytest.fixture(scope='session')
def mock_enable_unmanaged_for_testing():
    """A pytest fixture that enables unmanaged datasets for testing. Until unmanaged datasets are completed, they
    are disabled and dormant. We want to keep testing them and carry the code forward, but don't want them to be
    used yet.

    When running via a normal build, only "gigantum_object_v1" is available. To enable the others, you need to edit
    gtmcore.dataset.storage.SUPPORTED_STORAGE_BACKENDS in gtmcore.dataset.storage.__init__.py

    When this is done (unmanaged datasets are being re-activated) you should remove this fixture everywhere.
    """
    gtmcore.dataset.storage.SUPPORTED_STORAGE_BACKENDS = {
        "gigantum_object_v1": ("gtmcore.dataset.storage.gigantum", "GigantumObjectStore"),
        "local_filesystem": ("gtmcore.dataset.storage.local", "LocalFilesystem"),
        "public_s3_bucket": ("gtmcore.dataset.storage.s3", "PublicS3Bucket")}

    yield


class EnvironMock(object):
    """A simple class to mock the Flask environ object so you can have a token"""
    def __init__(self):
        self.environ = {'HTTP_AUTHORIZATION': "Bearer afaketoken"}


class ContextMock(object):
    """A simple class to mock the Flask request context so you have a labbook_loader attribute"""
    def __init__(self):
        self.labbook_loader = None
        self.headers = EnvironMock()


@pytest.fixture
def fixture_working_dir():
    """A pytest fixture that creates a temporary working directory, config file, schema, and local user identity
    """
    # Create temp dir
    config_instance, temp_dir = _create_temp_work_dir()

    # Create user identity
    insert_cached_identity(config_instance.app_workdir)

    # Create test client
    schema = graphene.Schema(query=LabbookQuery, mutation=LabbookMutations)

    # Load User identity into app context
    app = Flask("lmsrvlabbook")
    app.config["LABMGR_CONFIG"] = config = Configuration()
    app.config["ID_MGR_CLS"] = get_identity_manager_class(config)

    with app.app_context():
        # within this block, current_app points to app. Set current user explicitly(this is done in the middleware)
        flask.g.user_obj = get_identity_manager_class(config)(config).get_user_profile()
        flask.g.access_token = "afakeaccesstoken"
        flask.g.id_token = "afakeidtoken"

        # Create a test client
        client = Client(schema, middleware=[DataloaderMiddleware(), RepositoryCacheMiddleware()],
                        context_value=ContextMock())
        # name of the config file, temporary working directory (for the current server), the schema
        yield config_instance, temp_dir, client, schema

    # Remove the temp_dir
    config_instance.clear_cached_configuration()
    shutil.rmtree(temp_dir)


@pytest.fixture
def fixture_working_dir_dataset_tests(fixture_working_dir, mock_enable_unmanaged_for_testing):
    """A pytest fixture to enable all dataset types for testing only. This can be removed and should be replaced in all
    test functions with `fixture_working_dir` once unmanaged datasets are truely enabled.
    """
    yield fixture_working_dir


@pytest.fixture
def fixture_working_dir_lfs_disabled():
    """A pytest fixture that creates a temporary working directory, config file, schema, and local user identity
    """
    # Create temp dir
    config_instance, temp_dir = _create_temp_work_dir(lfs_enabled=False)

    # Create user identity
    insert_cached_identity(config_instance.app_workdir)

    # Create test client
    schema = graphene.Schema(query=LabbookQuery, mutation=LabbookMutations)

    # Load User identity into app context
    app = Flask("lmsrvlabbook")
    app.config["LABMGR_CONFIG"] = config = Configuration()
    app.config["ID_MGR_CLS"] = get_identity_manager_class(config)

    with app.app_context():
        # within this block, current_app points to app. Set current user explicitly(this is done in the middleware)
        flask.g.user_obj = get_identity_manager_class(config)(config).get_user_profile()
        flask.g.access_token = "afakeaccesstoken"
        flask.g.id_token = "afakeidtoken"

        # Create a test client
        client = Client(schema, middleware=[DataloaderMiddleware(), RepositoryCacheMiddleware()],
                        context_value=ContextMock())

        yield config_instance, temp_dir, client, schema

    # Remove the temp_dir
    config_instance.clear_cached_configuration()
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="class")
def fixture_working_dir_env_repo_scoped():
    """A pytest fixture that creates a temporary working directory, a config file to match, creates the schema,
    and populates the environment component repository.
    Class scope modifier attached
    """
    # Create temp dir
    config_instance, temp_dir = _create_temp_work_dir()

    # Create user identity
    insert_cached_identity(config_instance.app_workdir)

    # Create test client
    schema = graphene.Schema(query=LabbookQuery, mutation=LabbookMutations)

    # get environment data and index
    erm = RepositoryManager()
    erm.update_repositories()
    erm.index_repositories()

    # Load User identity into app context
    app = Flask("lmsrvlabbook")
    app.config["LABMGR_CONFIG"] = config = Configuration()
    app.config["ID_MGR_CLS"] = get_identity_manager_class(config)

    with app.app_context():
        # within this block, current_app points to app. Set current user explicitly (this is done in the middleware)
        flask.g.user_obj = get_identity_manager_class(config)(config).get_user_profile()
        flask.g.access_token = "afakeaccesstoken"
        flask.g.id_token = "afakeidtoken"

        # Create a test client
        client = Client(schema, middleware=[DataloaderMiddleware(), error_middleware, RepositoryCacheMiddleware()],
                        context_value=ContextMock())

        # name of the config file, temporary working directory (for current server), the schema
        yield config_instance, temp_dir, client, schema

    # Remove the temp_dir
    config_instance.clear_cached_configuration()
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="class")
def fixture_working_dir_populated_scoped():
    """A pytest fixture that creates a temporary working directory, a config file to match, creates the schema,
    and populates the environment component repository.
    Class scope modifier attached
    """

    # Flush here to clean out the Repository cache (used to store create/modify dates).
    redis.Redis(db=7).flushdb()

    # Create temp dir
    config_instance, temp_dir = _create_temp_work_dir()

    # Create user identity
    insert_cached_identity(config_instance.app_workdir)

    # Create test client
    schema = graphene.Schema(query=LabbookQuery, mutation=LabbookMutations)

    # Create a bunch of lab books
    im = InventoryManager()

    im.create_labbook('default', 'default', "labbook1", description="Cats labbook 1")
    time.sleep(1.1)

    im.create_labbook('default', 'default', "labbook2", description="Dogs labbook 2")
    time.sleep(1.1)

    im.create_labbook('default', 'default', "labbook3", description="Mice labbook 3")
    time.sleep(1.1)

    im.create_labbook('default', 'default', "labbook4", description="Horses labbook 4")
    time.sleep(1.1)

    im.create_labbook('default', 'default', "labbook5", description="Cheese labbook 5")
    time.sleep(1.1)

    im.create_labbook('default', 'default', "labbook6", description="Goat labbook 6")
    time.sleep(1.1)

    im.create_labbook('default', 'default', "labbook7", description="Turtle labbook 7")
    time.sleep(1.1)

    im.create_labbook('default', 'default', "labbook8", description="Lamb labbook 8")
    time.sleep(1.1)

    im.create_labbook('default', 'default', "labbook9", description="Taco labbook 9")
    time.sleep(1.1)

    im.create_labbook('test3', 'test3', "labbook-0", description="This should not show up.")

    # Load User identity into app context
    app = Flask("lmsrvlabbook")
    app.config["LABMGR_CONFIG"] = config = Configuration()
    app.config["ID_MGR_CLS"] = get_identity_manager_class(config)

    with app.app_context():
        # within this block, current_app points to app. Set current user explicitly (this is done in the middleware)
        flask.g.user_obj = get_identity_manager_class(config)(config).get_user_profile()
        flask.g.access_token = "afakeaccesstoken"
        flask.g.id_token = "afakeidtoken"

        # Create a test client
        client = Client(schema, middleware=[DataloaderMiddleware(), RepositoryCacheMiddleware()],
                        context_value=ContextMock())

        yield config_instance, temp_dir, client, schema

    # Remove the temp_dir
    config_instance.clear_cached_configuration()
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="class")
def fixture_working_dir_dataset_populated_scoped():
    """A pytest fixture that creates a temporary working directory, a config file to match, creates the schema,
    and populates the environment component repository.
    Class scope modifier attached
    """
    # Create temp dir
    config_instance, temp_dir = _create_temp_work_dir()

    # Create user identity
    insert_cached_identity(config_instance.app_workdir)

    # Create test client
    schema = graphene.Schema(query=LabbookQuery, mutation=LabbookMutations)

    # Create a bunch of lab books
    im = InventoryManager()

    im.create_dataset('default', 'default', "dataset2", storage_type="gigantum_object_v1", description="Cats 2")
    time.sleep(1.1)

    im.create_dataset('default', 'default', "dataset3", storage_type="gigantum_object_v1", description="Cats 3")
    time.sleep(1.1)

    im.create_dataset('default', 'default', "dataset4", storage_type="gigantum_object_v1", description="Cats 4")
    time.sleep(1.1)

    im.create_dataset('default', 'default', "dataset5", storage_type="gigantum_object_v1", description="Cats 5")
    time.sleep(1.1)

    im.create_dataset('default', 'default', "dataset6", storage_type="gigantum_object_v1", description="Cats 6")
    time.sleep(1.1)

    im.create_dataset('default', 'default', "dataset7", storage_type="gigantum_object_v1", description="Cats 7")
    time.sleep(1.1)

    im.create_dataset('default', 'default', "dataset8", storage_type="gigantum_object_v1", description="Cats 8")
    time.sleep(1.1)

    im.create_dataset('default', 'default', "dataset9", storage_type="gigantum_object_v1", description="Cats 9")
    time.sleep(1.1)

    im.create_dataset('default', 'test3', "dataset-other", storage_type="gigantum_object_v1", description="Cats other")
    time.sleep(1.1)

    im.create_labbook('test3', 'test3', "labbook-0", description="This should not show up.")

    im.create_dataset('default', 'default', "dataset1", storage_type="gigantum_object_v1", description="Cats 1")
    time.sleep(1.1)

    # Flush Redis cache for Repo info
    DatasetCacheController().clear_all()

    # Load User identity into app context
    app = Flask("lmsrvlabbook")
    app.config["LABMGR_CONFIG"] = config = Configuration()
    app.config["ID_MGR_CLS"] = get_identity_manager_class(config)

    with app.app_context():
        # within this block, current_app points to app. Set current user explicitly (this is done in the middleware)
        flask.g.user_obj = get_identity_manager_class(config)(config).get_user_profile()
        flask.g.access_token = "afakeaccesstoken"
        flask.g.id_token = "afakeidtoken"

        # Create a test client
        client = Client(schema, middleware=[DataloaderMiddleware(), RepositoryCacheMiddleware()],
                        context_value=ContextMock())

        yield config_instance, temp_dir, client, schema

    # Remove the temp_dir
    config_instance.clear_cached_configuration()
    shutil.rmtree(temp_dir)


@pytest.fixture
def fixture_single_dataset():
    """A pytest fixture that creates a temporary working directory, a config file to match, creates the schema,
    and populates the environment component repository.
    Class scope modifier attached
    """
    # Create temp dir
    config_instance, temp_dir = _create_temp_work_dir()

    # Create user identity
    insert_cached_identity(config_instance.app_workdir)

    # Create test client
    schema = graphene.Schema(query=LabbookQuery, mutation=LabbookMutations)

    # Create a bunch of lab books
    im = InventoryManager()

    ds = im.create_dataset('default', 'default', "test-dataset", storage_type="gigantum_object_v1", description="Cats 2")
    m = Manifest(ds, 'default')
    cm_class = get_cache_manager_class(ds.client_config)
    cache_mgr = cm_class(ds, 'default')
    revision = ds.git.repo.head.commit.hexsha

    os.makedirs(os.path.join(cache_mgr.cache_root, revision, "other_dir"))
    helper_append_file(cache_mgr.cache_root, revision, "test1.txt", "asdfasdf")
    helper_append_file(cache_mgr.cache_root, revision, "test2.txt", "rtg")
    helper_append_file(cache_mgr.cache_root, revision, "test3.txt", "wer")
    helper_append_file(cache_mgr.cache_root, revision, "other_dir/test4.txt", "dfasdfhfgjhg")
    helper_append_file(cache_mgr.cache_root, revision, "other_dir/test5.txt", "fdghdfgsa")
    m.update()

    # Load User identity into app context
    app = Flask("lmsrvlabbook")
    app.config["LABMGR_CONFIG"] = config = Configuration()
    app.config["ID_MGR_CLS"] = get_identity_manager_class(config)

    with app.app_context():
        # within this block, current_app points to app. Set current user explicitly (this is done in the middleware)
        flask.g.user_obj = get_identity_manager_class(config)(config).get_user_profile()
        flask.g.access_token = "afakeaccesstoken"
        flask.g.id_token = "afakeidtoken"

        # Create a test client
        client = Client(schema, middleware=[DataloaderMiddleware(), RepositoryCacheMiddleware()], context_value=ContextMock())

        yield config_instance, temp_dir, client, ds, cache_mgr

    # Remove the temp_dir
    config_instance.clear_cached_configuration()
    shutil.rmtree(temp_dir)


@pytest.fixture(scope='class')
def build_image_for_jupyterlab():
    # Create temp dir
    config_instance, temp_dir = _create_temp_work_dir()

    # Create user identity
    insert_cached_identity(config_instance.app_workdir)

    # Create test client
    schema = graphene.Schema(query=LabbookQuery, mutation=LabbookMutations)

    # get environment data and index
    erm = RepositoryManager()
    erm.update_repositories()
    erm.index_repositories()

    # Load User identity into app context
    app = Flask("lmsrvlabbook")
    app.config["LABMGR_CONFIG"] = config = Configuration()
    app.config["ID_MGR_CLS"] = get_identity_manager_class(config)

    with app.app_context():
        # within this block, current_app points to app. Set current user explicitly (this is done in the middleware)
        flask.g.user_obj = get_identity_manager_class(config)(config).get_user_profile()

        # Create a test client
        client = Client(schema, middleware=[DataloaderMiddleware(), error_middleware, RepositoryCacheMiddleware()],
                        context_value=ContextMock())

        # Create a labook
        im = InventoryManager()
        lb = im.create_labbook('default', 'unittester', "containerunittestbook",
                               description="Testing docker building.")
        cm = ComponentManager(lb)
        cm.add_base(ENV_UNIT_TEST_REPO, ENV_UNIT_TEST_BASE, ENV_UNIT_TEST_REV)
        cm.add_packages("pip3", [{"manager": "pip3", "package": "requests", "version": "2.18.4"}])

        bam = BundledAppManager(lb)
        bam.add_bundled_app(9999, 'share', 'A bundled app for testing', "cd /mnt; python3 -m http.server 9999")

        ib = ImageBuilder(lb)
        ib.assemble_dockerfile(write=True)

        container_ops = container_for_context(username="default", labbook=lb)
        # We are not currently concerned with running these tests on the cloud context
        docker_client = container_ops._client

        try:
            container_ops.build_image()
            docker_image_id = container_ops._image_id

            # Note: The final field is the owner
            yield lb, ib, docker_client, docker_image_id, client, "unittester"

        finally:
            try:
                docker_client.containers.get(docker_image_id).stop()
                docker_client.containers.get(docker_image_id).remove()
            except:
                pass

            try:
                docker_client.images.remove(docker_image_id, force=True, noprune=False)
            except:
                pass

            config_instance.clear_cached_configuration()
            shutil.rmtree(lb.root_dir)


@pytest.fixture()
def mock_create_labbooks(fixture_working_dir):
    # Create a temporary labbook
    lb = InventoryManager().create_labbook("default", "default", "labbook1", description="Cats labbook 1")

    # Create a file in the dir
    with open(os.path.join(fixture_working_dir[1], 'sillyfile'), 'w') as sf:
        sf.write("1234567")
        sf.seek(0)
    FileOperations.insert_file(lb, 'code', sf.name)

    assert os.path.isfile(os.path.join(lb.root_dir, 'code', 'sillyfile'))
    # name of the config file, temporary working directory, the schema
    yield fixture_working_dir


@pytest.fixture(scope='class')
def build_image_for_rserver():
    pass


@pytest.fixture
def fixture_test_file():
    """A pytest fixture that creates a temporary file
    """
    temp_file_name = os.path.join(tempfile.tempdir, "test_file.txt")
    with open(temp_file_name, 'wt') as dummy_file:
        dummy_file.write("blah")
        dummy_file.flush()
        dummy_file.seek(0)

        yield dummy_file.name

    try:
        os.remove(temp_file_name)
    except:
        pass


@pytest.fixture()
def property_mocks_fixture():
    """A pytest fixture that returns a GitLabRepositoryManager instance"""
    responses.add(responses.POST, 'https://test.gigantum.com/api/v1/',
                      json={'data': {'additionalCredentials': {'gitServiceToken': 'afaketoken'}}}, status=200)
    responses.add(responses.GET, 'https://test.repo.gigantum.com/api/v4/projects?search=labbook1',
                  json=[{
                          "id": 26,
                          "description": "",
                        }],
                  status=200, match_querystring=True)
    yield


@pytest.fixture()
def docker_socket_fixture():
    """Helper method to get the docker client version"""

    client = get_docker_client()
    version = client.version()['ApiVersion']

    if "CIRCLECI" in os.environ:
        docker_host = os.environ['DOCKER_HOST']
        docker_host = docker_host.replace("tcp", "https")
        responses.add_passthru(
            f"{docker_host}/v{version}/images/default-default-labbook1/json")
        responses.add_passthru(
            f"{docker_host}/v{version}/containers/default-default-labbook1/json")
        responses.add_passthru(
            f"{docker_host}/v{version}/images/default-default-labbook1/json")
        responses.add_passthru(
            f"{docker_host}/v{version}/containers/default-default-labbook1/json")
        responses.add_passthru(
            f"{docker_host}/v{version}/images/default-test-sample-repo-lb/json")
        responses.add_passthru(
            f"{docker_host}/v{version}/containers/default-test-sample-repo-lb/json")
        responses.add_passthru(
            '{docker_host}/v{version}/containers/default-test-sample-repo-lb/json')
    else:
        responses.add_passthru(
            f"http+docker://localunixsocket/v{version}/images/default-default-labbook1/json")
        responses.add_passthru(
            f"http+docker://localunixsocket/v{version}/containers/default-default-labbook1/json")
        responses.add_passthru(
            f"http+docker://localunixsocket/v{version}/images/default-test-sample-repo-lb/json")
        responses.add_passthru(
            f"http+docker://localunixsocket/v{version}/containers/default-test-sample-repo-lb/json")

    yield
