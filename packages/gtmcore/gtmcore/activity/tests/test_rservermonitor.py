from gtmcore.mitmproxy.mitmproxy import CURRENT_MITMPROXY_TAG, MITMProxyOperations
import os

from gtmcore.activity.tests.fixtures import get_redis_client_mock, redis_client, MockSessionsResponse
from gtmcore.fixtures import mock_labbook
from gtmcore.activity import ActivityStore
from gtmcore.container import container_for_context

from gtmcore.activity.monitors.monitor_rserver import RServerMonitor, RStudioServerMonitor

def mock_ip(key):
    return "172.0.1.2"

class TestRServerMonitor:

    def test_setup(self, redis_client):
        """Test getting the supported names of the dev env monitor"""
        monitor = RServerMonitor()

        assert len(monitor.get_dev_env_name()) == 1
        assert 'rstudio' in monitor.get_dev_env_name()


class TestRStudioServerMonitor:

    def test_init(self, redis_client, mock_labbook):
        """Test getting the supported names of the dev env monitor"""
    
        server_monitor = RStudioServerMonitor("test", "test", mock_labbook[2].name,
                                            "52f5a3a9", config_file=mock_labbook[0])
        assert len(server_monitor.processors) == 6

    def test_code_and_image(self, redis_client, mock_labbook):
        """Test reading a log and storing a record"""
    
        # create a server monitor 
        server_monitor = RStudioServerMonitor("test", "test", mock_labbook[2].name,
                                            "foo:activity_monitor:52f5a3a9", config_file=mock_labbook[0])

        mitmlog = open(f"{os.path.dirname(os.path.realpath(__file__))}/52f5a3a9.rserver.dump", "rb")

        # Read activity and return an aggregated activity record
        server_monitor.process_activity(mitmlog)
        # call processor
        server_monitor.store_record() 

        a_store = ActivityStore(mock_labbook[2])
        ars = a_store.get_activity_records()

        # details object [x][3] gets the x^th object
        code_dict = a_store.get_detail_record(ars[0]._detail_objects[1][3].key).data

        # check the code results
        assert(code_dict['text/markdown'][101:109] == 'y("knitr')

        # check part of an image
        imgdata = a_store.get_detail_record(ars[1]._detail_objects[1][3].key).data['image/png'][0:20]
        assert(imgdata == '/9j/4AAQSkZJRgABAQAA')

    def test_multiplecells(self, redis_client, mock_labbook):
        """Make sure that RStudio detects and splits cells"""

        server_monitor = RStudioServerMonitor("test", "test", mock_labbook[2].name,
                                            "foo:activity_monitor:73467b78", config_file=mock_labbook[0])

        mitmlog = open(f"{os.path.dirname(os.path.realpath(__file__))}/73467b78.rserver.dump", "rb")

        # Read activity and return an aggregated activity record
        server_monitor.process_activity(mitmlog)
        # call processor
        server_monitor.store_record() 

        a_store = ActivityStore(mock_labbook[2])
        ars = a_store.get_activity_records()

        # details object [x][3] gets the x^th object
        cell_1 = a_store.get_detail_record(ars[0]._detail_objects[2][3].key).data
        cell_2 = a_store.get_detail_record(ars[0]._detail_objects[3][3].key).data

        # if the cells were divided, there will be two records
        assert(cell_1['text/plain'][55:58] == 'pop')
        assert(cell_2['text/plain'][200:204] == 'stan')


class TestMITMproxy:

    def test_start_mitm_proxy(self, redis_client, mock_labbook):
        # The name of the MITM proxy container is simply the target container prefixed with gmitmproxy
        # E.g., gmitmproxy.gmlb-tinydav-tinydav-rstudio-test
        labbook_name = 'wholly-irrelevant'
        username = 'soycapitan'
        mitm_name = f"gmitmproxy.{labbook_name}"

        container_ops = container_for_context(username)
        # Ensure this container doesn't exist already
        container_ops.stop_container(mitm_name)

        # The below image should ideally already be on the system, maybe not tagged
        # If not, it'll hopefully be useful later - we won't clean it up
        image_name = 'ubuntu:18.04'

        # We still use Docker directly here. Doesn't make sense to create an abstraction that's only used by a test
        docker_client = container_ops._client
        docker_client.images.pull(image_name)
        docker_client.containers.create(image_name, name=mitm_name)

        # This gets all the containers that are based on our current mitmproxy image
        clist = container_ops.container_list('gigantum/mitmproxy_proxy:' + CURRENT_MITMPROXY_TAG)
        # If our mitm_name'd container shows up there, it's a properly deployed MITM Proxy (it's not yet)
        assert mitm_name not in clist

        MITMProxyOperations.start_mitm_proxy(username, 'http://127.0.0.1:8787', labbook_name)

        clist = container_ops.container_list('gigantum/mitmproxy_proxy:' + CURRENT_MITMPROXY_TAG)
        assert mitm_name in clist

        MITMProxyOperations.stop_mitm_proxy(username, labbook_name)

        if container_ops.stop_container(mitm_name):
            assert False, "MITM container not cleaned up during `stop_mitm_proxy()`"
