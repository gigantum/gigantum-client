import uuid
from urllib.parse import quote_plus
import graphene
import redis
import os

from confhttpproxy import ProxyRouter

from gtmcore.inventory.inventory import InventoryManager
from gtmcore.labbook.labbook import LabBook
from gtmcore.exceptions import GigantumException
from gtmcore.container import container_for_context
from gtmcore.mitmproxy.mitmproxy import MITMProxyOperations
from gtmcore.container.jupyter import check_jupyter_reachable, start_jupyter
from gtmcore.container.rserver import start_rserver, check_rstudio_reachable
from gtmcore.container.bundledapp import start_bundled_app, check_bundled_app_reachable
from gtmcore.logging import LMLogger
from gtmcore.activity.services import start_labbook_monitor
from gtmcore.environment.bundledapp import BundledAppManager

from lmsrvcore.auth.user import get_logged_in_username, get_logged_in_author

logger = LMLogger.get_logger()


def unique_id() -> str:
    """This is used to, e.g., identify a specific running labbook.

    This allows us to link things like activity monitors, etc.
    It can safely be improved or changed, as consumers should only expect some "random" string."""
    return uuid.uuid4().hex[:10]


class StartDevTool(graphene.relay.ClientIDMutation):
    class Input:
        owner = graphene.String(required=True)
        labbook_name = graphene.String(required=True)
        dev_tool = graphene.String(required=True)
        container_override_id = graphene.String(required=False)

    # Return the Environment instance
    path = graphene.String()

    @classmethod
    def _start_dev_tool(cls, labbook: LabBook, username: str, dev_tool: str, container_override_id: str = None):
        router = ProxyRouter.get_proxy(labbook.client_config.config['proxy'])
        bam = BundledAppManager(labbook)
        bundled_apps = bam.get_bundled_apps()
        bundled_app_names = [x for x in bundled_apps]

        if dev_tool == "rstudio":
            suffix = cls._start_rstudio(labbook, router, username)
        elif dev_tool in ["jupyterlab", "notebook"]:
            # Note that starting the dev tool is identical whether we're targeting jupyterlab or notebook
            suffix = cls._start_jupyter_tool(labbook, router, username, container_override_id)
        elif dev_tool in bundled_app_names:
            app_data = bundled_apps[dev_tool]
            app_data['name'] = dev_tool
            suffix = cls._start_bundled_app(labbook, router, username, app_data, container_override_id)
        else:
            raise GigantumException(f"'{dev_tool}' not currently supported as a Dev Tool")

        # Don't include the port in the path if running on 80
        apparent_proxy_port = labbook.client_config.config['proxy']["apparent_proxy_port"]
        if apparent_proxy_port == 80:
            # Running on 80, don't need the port
            path = suffix
        elif labbook.client_config.is_hub_client:
            # Running in hub, don't prepend a port
            path = suffix
        else:
            path = f':{apparent_proxy_port}{suffix}'

        return path

    @classmethod
    def _start_jupyter_tool(cls, labbook: LabBook, router: ProxyRouter, username: str,
                            container_override_id: str = None):
        tool_port = 8888
        # Recall that we re-use the image name for Projects as the container name
        project_container = container_for_context(username, labbook=labbook, override_image_name=container_override_id)
        labbook_ip = project_container.query_container_ip()
        labbook_endpoint = f'http://{labbook_ip}:{tool_port}'

        # Set route prefix to jupyter based on if you are running locally or in a hub
        if labbook.client_config.is_hub_client:
            jupyter_prefix = f"/run/{os.environ['GIGANTUM_CLIENT_ID']}/jupyter"
        else:
            jupyter_prefix = f'/jupyter'

        matched_routes = router.get_matching_routes(labbook_endpoint, jupyter_prefix)

        # The "suffix" is the relative route to return to the browser for the user
        suffix = None
        # The "external_rt_prefix" is the external route to jupyter (just to the server, so you can do things like hit
        # the jupyter API or build a full "suffix")
        if len(matched_routes) == 0:
            # We are starting jupyter for the first time
            external_rt_prefix = f"{jupyter_prefix}/{unique_id()}"
            run_start_jupyter = True

        elif len(matched_routes) == 1:
            # A route to jupyter was found in the route table
            logger.info(f'Found existing Jupyter instance in route table for {str(labbook)}.')

            # Load the jupyter token out of redis, if available
            redis_conn = redis.Redis(db=1)
            token = redis_conn.get(f"{project_container.image_tag}-jupyter-token")
            if token:
                token_str = f"token={token.decode()}"
            else:
                token_str = ""

            # Verify jupyter API is available and it's still running.
            suffix = matched_routes[0]
            external_rt_prefix = suffix
            try:
                check_jupyter_reachable(labbook_ip, tool_port, suffix)

                # Add token on for the user before sending back, if available. Don't re-start the Jupyter process
                suffix = f'{suffix}/lab/tree/code?{token_str}'
                run_start_jupyter = False

            except GigantumException:
                # If you get here, the Jupyter API didn't respond, so it's probably a stale route.
                logger.warning(f'Detected stale route. Attempting to restart Jupyter and clean up route table.')
                # Remove stale route
                router.remove(suffix)
                # Delete the token from redis
                redis_conn.delete(f"{project_container.image_tag}-jupyter-token")

                # Try re-starting jupyter
                run_start_jupyter = True

        else:
            raise ValueError(f"Multiple Jupyter instances found in route table for {str(labbook)}! Restart container.")

        if run_start_jupyter:
            # Add route
            router.add(labbook_endpoint, external_rt_prefix)

            # Start jupyterlab
            suffix = start_jupyter(project_container, proxy_prefix=external_rt_prefix)

        # Ensure we start monitor it it isn't already running. This method will exit without scheduling a
        # dev env monitory if the dev env monitor for this jupyter instance is already running.
        start_labbook_monitor(labbook, username, 'jupyterlab',
                              url=f'{labbook_endpoint}{external_rt_prefix}',
                              author=get_logged_in_author())

        return suffix

    @classmethod
    def _start_rstudio(cls, labbook: LabBook, router: ProxyRouter, username: str,
                       container_override_id: str = None):

        # All messages will come through MITM, so we don't need to monitor rserver directly
        project_container = container_for_context(username, labbook, override_image_name=container_override_id)
        fresh_rserver = start_rserver(project_container)
        mitm_url, pr_suffix = MITMProxyOperations.configure_mitmroute(project_container, router, fresh_rserver)

        # Ensure monitor is running
        start_labbook_monitor(labbook, username, "rstudio",
                              # the endpoint for the NGINX proxy running inside the mitmproxy container
                              # (not the rserver) which maps `/rserver/<whatever>/<foo>` to `/<foo>`.
                              # But url isn't used currently by monitor_rserver.RServerMonitor!
                              url=mitm_url,
                              author=get_logged_in_author())

        check_rstudio_reachable(mitm_url)

        return pr_suffix

    @classmethod
    def _start_bundled_app(cls, labbook: LabBook, router: ProxyRouter, username: str, bundled_app: dict,
                           container_override_id: str = None):
        tool_port = bundled_app['port']
        project_container = container_for_context(username, labbook=labbook)
        labbook_ip = project_container.query_container_ip()
        endpoint = f'http://{labbook_ip}:{tool_port}'

        route_prefix = f"/{quote_plus(bundled_app['name'])}"

        matched_routes = router.get_matching_routes(endpoint, route_prefix)

        run_command = True
        suffix = None
        if len(matched_routes) == 1:
            logger.info(f"Found existing {bundled_app['name']} in route table for {str(labbook)}.")
            suffix = matched_routes[0]
            run_command = False

        elif len(matched_routes) > 1:
            raise ValueError(f"Multiple {bundled_app['name']} instances found in route table "
                             f"for {str(labbook)}! Restart container.")

        if run_command:
            external_rt_prefix = f"{route_prefix}/{unique_id()}"
            logger.info(f"Adding {bundled_app['name']} to route table for {str(labbook)}.")
            suffix, _ = router.add(endpoint, external_rt_prefix)
            suffix = f"/{suffix}"

            # Start app
            logger.info(f"Starting {bundled_app['name']} in {str(labbook)}.")
            start_bundled_app(labbook, username, bundled_app['command'], external_rt_prefix, tag=container_override_id)

            # Wait for the app to start
            check_bundled_app_reachable(bundled_app['name'], labbook_ip, tool_port, external_rt_prefix, 200)

        return suffix

    @classmethod
    def mutate_and_get_payload(cls, root: str, info: str, owner: str, labbook_name: str, dev_tool: str,
                               container_override_id: str = None, client_mutation_id: str = None):
        username = get_logged_in_username()
        labbook = InventoryManager().load_labbook(username, owner, labbook_name,
                                                  author=get_logged_in_author())

        with labbook.lock(failfast=True):
            path = cls._start_dev_tool(labbook, username, dev_tool.lower(), container_override_id)

        return StartDevTool(path=path)
