import multiprocessing
import os
import pprint
import pytest
import shutil
import time

from mock import patch
import requests

from gtmcore.environment import ComponentManager
from gtmcore.dispatcher import Dispatcher, JobKey
from gtmcore.inventory.inventory import InventoryManager
from lmsrvlabbook.tests.fixtures import fixture_working_dir_env_repo_scoped, fixture_working_dir
from gtmcore.fixtures import ENV_UNIT_TEST_REPO, ENV_UNIT_TEST_BASE, ENV_UNIT_TEST_REV


import service


@pytest.fixture()
def start_server():
    pass


class SampleMockObject(object):
    def method_to_mock(self):
        with open('/tmp/cats', 'w') as f:
            f.write("If you see this file, things didn't work")


def mocky(self):
    with open('/tmp/dogs', 'w') as f:
        f.write("This indicates the mocking in a subprocess worked!")


def invoker():
    return SampleMockObject().method_to_mock()


@pytest.fixture(scope="session")
def pause():
    time.sleep(3)


class TestLabbookMutation(object):
    def test_mocking_in_subprocess(self):
        # This test should remain to validate that mocking applies to classes
        # loaded by a sub-process of this pytest process.
        if os.path.exists('/tmp/cats'):
            os.remove('/tmp/cats')
        if os.path.exists('/tmp/dogs'):
            os.remove('/tmp/dogs')
        with patch.object(SampleMockObject, 'method_to_mock', mocky):
            assert not os.path.exists('/tmp/cats')
            proc = multiprocessing.Process(target=invoker)
            proc.daemon = True
            proc.start()
            time.sleep(1)
            assert not os.path.exists('/tmp/cats')
            assert os.path.exists('/tmp/dogs')

    def test_launch_api_server(self, pause, fixture_working_dir_env_repo_scoped):
        proc = multiprocessing.Process(target=service.main, kwargs={'debug': False})
        proc.daemon = True
        proc.start()

        time.sleep(4)
        assert proc.is_alive()
        proc.terminate()

    def test_export_and_import_lb(self, fixture_working_dir_env_repo_scoped):
        workdir, _, _ = fixture_working_dir_env_repo_scoped[1].rsplit('/', 2)
        os.environ['HOST_WORK_DIR'] = workdir

        api_server_proc = multiprocessing.Process(target=service.main, kwargs={'debug': False})
        api_server_proc.daemon = True
        api_server_proc.start()
        time.sleep(5)
        assert api_server_proc.is_alive()

        lb_name = "mutation-export-import-unittest"
        im = InventoryManager()
        lb = im.create_labbook("default", "default", lb_name, description="Import/Export Mutation Testing.")
        cm = ComponentManager(lb)
        cm.add_base(ENV_UNIT_TEST_REPO, 'ut-busybox', 0)

        assert api_server_proc.is_alive()
        export_query = """
        mutation export {
          exportLabbook(input: {
            owner: "default",
            labbookName: "%s"
          }) {
            jobKey
          }
        }
        """ % lb.name
        r = fixture_working_dir_env_repo_scoped[2].execute(export_query)
        pprint.pprint(r)

        # Sleep while the background job completes, and then delete new lb.
        time.sleep(5)
        d = Dispatcher()
        job_status = d.query_task(JobKey(r['data']['exportLabbook']['jobKey']))

        # Delete existing labbook in file system.
        shutil.rmtree(lb.root_dir)
        assert api_server_proc.is_alive()

        assert job_status.status == 'finished'
        assert not os.path.exists(lb.root_dir)
        assert os.path.exists(job_status.result)

        if os.path.exists(os.path.join('/tmp', os.path.basename(job_status.result))):
            os.remove(os.path.join('/tmp', os.path.basename(job_status.result)))
        new_path = shutil.move(job_status.result, '/tmp')

        # Now, import the labbook that was just exported.
        export_query = """
        mutation import {
          importLabbook(input: {
          }) {
            jobKey
          }
        }
        """

        files = {'uploadFile': open(new_path, 'rb')}
        qry = {"query": export_query}
        assert api_server_proc.is_alive()
        r = requests.post('http://localhost:10001/labbook/', data=qry, files=files)
        time.sleep(0.5)
        assert 'errors' not in r
