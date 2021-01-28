from typing import Optional
import requests
import time

from gtmcore.container import container_for_context
from gtmcore.labbook import LabBook
from gtmcore.exceptions import GigantumException
from gtmcore.logging import LMLogger

logger = LMLogger.get_logger()


def start_bundled_app(labbook: LabBook, username: str, command: str, route_prefix: str,
                      tag: Optional[str] = None) -> None:
    """ Method to start a bundled app by running the user specified command inside the running Project container

    Args:
        labbook: labbook instance
        username: current logged in user
        command: user specified command to run
        route_prefix: prefix the app is running on through the proxy
        tag: optional tag for the container override id

    Returns:
        None
    """
    if len(command) == 0:
        return

    proj_container = container_for_context(username, labbook=labbook)

    if proj_container.query_container() != 'running':
        raise GigantumException(f"{str(labbook)} container is not running. Start it before starting a bundled app.")

    command = f"export PATH=$CONDA_DIR/bin:$PATH && export APP_PREFIX={route_prefix} && {command}"
    logger.info(f"Starting custom app with command: {command}")
    proj_container.exec_command(command, user='giguser', get_results=False)


def check_bundled_app_reachable(app_name: str, ip_address: str, port: int, prefix: str, expected_status: int = 200):
    test_url = f'http://{ip_address}:{port}{prefix}'

    for n in range(30):
        logger.debug(f"Attempt {n + 1}: Testing if custom app `{app_name}` is up at {test_url}...")
        try:
            r = requests.get(test_url, timeout=0.5)
            if r.status_code != expected_status:
                logger.info(f"app status {r.status_code}")
                time.sleep(0.5)
            else:
                logger.info(f'Found custom app `{app_name}` up at {test_url} after {n / 2.0} seconds')
                break

        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            # Assume API isn't up at all yet, so no connection can be made
            time.sleep(0.5)
    else:
        raise GigantumException(f'Could not reach custom app `{app_name}` after timeout')
