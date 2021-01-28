import pytest
import os
import getpass
import docker
import time
import shutil
import tempfile

from gtmcore.container.container import SidecarContainerOperations
from gtmcore.container.jupyter import start_jupyter
from gtmcore.container.rserver import start_rserver
from gtmcore.container.bundledapp import start_bundled_app

from gtmcore.container import container_for_context

from gtmcore.fixtures.container import build_lb_image_for_jupyterlab, build_lb_image_for_rstudio, mock_config_with_repo, ContainerFixture
from gtmcore.container.exceptions import ContainerBuildException
from gtmcore.environment.bundledapp import BundledAppManager


def remove_image_cache_data():
    try:
        shutil.rmtree('/mnt/gigantum/.labmanager/image-cache', ignore_errors=True)
    except:
        pass


class TestContainerOps:
    def test_build_image_fixture(self, build_lb_image_for_jupyterlab):
        # Note, the test is in the fixure (the fixture is needed by other tests around here).
        pass

    def test_start_jupyterlab(self, build_lb_image_for_jupyterlab):
        container_id = build_lb_image_for_jupyterlab[4]
        docker_image_id = build_lb_image_for_jupyterlab[3]
        client = build_lb_image_for_jupyterlab[2]
        ib = build_lb_image_for_jupyterlab[1]
        lb = build_lb_image_for_jupyterlab[0]

        # This is already created inside the fixture, but because of the way tuples are used,
        # it's too cumbersome to change the (widely-used) fixture to pass it back
        jupyter_container = container_for_context('unittester', lb)
        stdo = jupyter_container.exec_command('pgrep jupyter', get_results=True)
        l = [a for a in stdo.split('\n') if a]
        assert len(l) == 0

        start_jupyter(jupyter_container, check_reachable=not (getpass.getuser() == 'circleci'))

        stdo = jupyter_container.exec_command('pgrep jupyter', get_results=True)
        l = [a for a in stdo.split('\n') if a]
        assert len(l) == 1

        # Now, we test the second path through, start jupyterlab when it's already running.
        start_jupyter(jupyter_container, check_reachable=not (getpass.getuser() == 'circleci'))

        # Validate there is only one instance running.
        stdo = jupyter_container.exec_command('pgrep jupyter', get_results=True)
        l = [a for a in stdo.split('\n') if a]
        assert len(l) == 1

    def test_start_rstudio(self, build_lb_image_for_rstudio):
        lb_container, ib, username = build_lb_image_for_rstudio

        assert len(lb_container.ps_search('rserver')) == 0

        start_rserver(lb_container, check_reachable=not (getpass.getuser() == 'circleci'))
        time.sleep(5)
        
        assert len(lb_container.ps_search('rserver')) == 1
        # Now, we test the second path through, start jupyterlab when it's already running.
        start_rserver(lb_container, check_reachable=not (getpass.getuser() == 'circleci'))

        # Validate there is still only one instance running.
        assert len(lb_container.ps_search('rserver')) == 1

    def test_run_command(self, build_lb_image_for_jupyterlab):
        my_lb = build_lb_image_for_jupyterlab[0]
        docker_image_id = build_lb_image_for_jupyterlab[3]

        proj_container = container_for_context("unittester", labbook=my_lb)
        result = proj_container.exec_command("echo My sample message", get_results=True)
        assert result.strip() == 'My sample message'

        result = proj_container.exec_command("pip freeze", get_results=True)
        assert "conda" in result
        assert "notebook" in result

        result = proj_container.exec_command("/bin/true", get_results=True)
        assert result.strip() == ""

        result = proj_container.exec_command("/bin/false", get_results=True)
        assert result.strip() == ""

    def test_old_dockerfile_removed_when_new_build_fails(self, build_lb_image_for_jupyterlab):
        # Test that when a new build fails, old images are removed so they cannot be launched.
        my_lb = build_lb_image_for_jupyterlab[0]
        docker_client = build_lb_image_for_jupyterlab[2]

        proj_container = container_for_context("unittester", labbook=my_lb)
        proj_container.stop_container()

        assert proj_container.query_container() is None

        olines = open(os.path.join(my_lb.root_dir, '.gigantum/env/Dockerfile')).readlines()[:6]
        with open(os.path.join(my_lb.root_dir, '.gigantum/env/Dockerfile'), 'w') as dockerfile:
            dockerfile.write('\n'.join(olines))
            dockerfile.write('\nRUN /bin/false')

        # We need to remove cache data otherwise the following tests won't work
        remove_image_cache_data()

        with pytest.raises(ContainerBuildException):
            proj_container.build_image()

        with pytest.raises(docker.errors.ImageNotFound):
            docker_client.images.get(proj_container.image_tag)

        with pytest.raises(docker.errors.ImageNotFound):
            # Image not found so container cannot be started
            proj_container.start_project_container()


class TestSidecarContainers:
    def test_all_sidecar_container_ops(self):
        """We test all functions at once because start and stop is expensive, and also requried to test other stuff"""
        primary_container = container_for_context('unittester', override_image_name='necessary-detail')
        sidecar_container = SidecarContainerOperations(primary_container, 'support')
        assert sidecar_container.sidecar_container_name == 'support.necessary-detail'
        # Just in case
        sidecar_container.stop_container()
        assert sidecar_container.query_container() is None

        # The below image should ideally already be on the system, maybe not tagged
        # If not, it'll hopefully be useful later - we won't clean it up
        image_name = 'ubuntu:18.04'

        # We still use Docker directly here. Doesn't make sense to create an abstraction that's only used by a test
        docker_client = primary_container._client
        docker_client.images.pull(image_name)

        sidecar_container.run_container(image_name, cmd='tail -f /dev/null')

        try:
            assert sidecar_container.query_container() == 'running'
            assert len(sidecar_container.ps_search('tail')) == 1
            assert len(sidecar_container.query_container_ip().split('.')) == 4
            assert len(sidecar_container.query_container_env()) > 0
        finally:
            sidecar_container.stop_container()

        assert sidecar_container.query_container() is None


class TestPutFile:
    def test_put_single_file(self, build_lb_image_for_jupyterlab):
        # Note - we are combining multiple tests in one to speed things up
        # We do not want to build, start, execute, stop, and delete at container for each
        # of the following test points.
        fixture = ContainerFixture(build_lb_image_for_jupyterlab)

        # Test insert of a single file.
        dst_dir_1 = "/home/giguser/sample-creds"
        with tempfile.TemporaryDirectory() as tempdir:
            with open(os.path.join(tempdir, 'secretfile'), 'w') as sample_secret:
                sample_secret.write("<<Secret File Content>>")
            t0 = time.time()
            proj_container = container_for_context(fixture.username, labbook=fixture.labbook)
            proj_container.copy_into_container(src_path=sample_secret.name, dst_dir=dst_dir_1)
            tf = time.time()
            proj_container.exec_command("cat {dst_dir_1}/secretfile")

            # The copy_into_container should NOT remove the original file on disk.
            assert os.path.exists(sample_secret.name)
            assert tf - t0 < 1.0, \
                f"Time to insert small file must be less than 1 sec - took {tf-t0:.2f}s"

    def test_start_bundled_app(self, build_lb_image_for_jupyterlab):
        test_file_path = "/tmp/test.txt"

        lb = build_lb_image_for_jupyterlab[0]

        client = docker.from_env()
        container = client.containers.get(build_lb_image_for_jupyterlab[4])
        result = container.exec_run(f"cat {test_file_path}")
        assert result.exit_code == 1
        assert "No such file" in result.output.decode()

        bam = BundledAppManager(lb)
        bam.add_bundled_app(9002, 'my app', 'tester', f"echo 'teststr' >> {test_file_path}")
        apps = bam.get_bundled_apps()

        start_bundled_app(lb, 'unittester', apps['my app']['command'], "")

        time.sleep(3)

        result = container.exec_run(f"cat {test_file_path}")
        assert result.exit_code == 0
        assert "teststr" in result.output.decode()


