#!/usr/bin/python3

import shutil
import os
import base64
from time import sleep

import flask

import requests.exceptions
import blueprint
from flask_cors import CORS
from confhttpproxy import ProxyRouter, ProxyRouterException
from flask import Flask, jsonify

import rest_routes
from lmsrvcore.utilities.migrate import migrate_work_dir_structure_v2
from gtmcore.dispatcher import Dispatcher
from gtmcore.dispatcher.jobs import update_environment_repositories
from gtmcore.configuration import Configuration
from gtmcore.logging import LMLogger
from gtmcore.auth.identity import AuthenticationError, get_identity_manager_class
from gtmcore.labbook.lock import reset_all_locks


logger = LMLogger.get_logger()


def configure_chp(proxy_dict: dict, is_hub_client: bool) -> str:
    """Set up the configurable HTTP proxy (CHP)

    Args:
        proxy_dict: obtained from the config dict inside the config instance
        is_hub_client: are we running on the hub? (also obtained from config instance)

    Returns:
        the final api_prefix used by the router

    We define this as a function mostly so we can optionally wrap it in a try block below
    """
    # /api by default
    api_prefix = proxy_dict["labmanager_api_prefix"]

    proxy_router = ProxyRouter.get_proxy(proxy_dict)
    # Wait up to 10 seconds for the CHP to be available
    for _ in range(20):
        try:
            # This property raises an exception if the underlying request doesn't yield a status code of 200
            proxy_router.routes  # noqa
        except (requests.exceptions.ConnectionError, ProxyRouterException):
            sleep(0.5)
            continue

        # If there was no exception, the CHP is up and responding
        break
    else:
        # We exhausted our for-loop
        logger.error("Could not reach router after 20 tries (10 seconds), proxy_router.add() will likely fail")

    if is_hub_client:
        # Use full route prefix, including run/<client_id> if running in the Hub
        api_target = f"run/{os.environ['GIGANTUM_CLIENT_ID']}{api_prefix}"
        api_prefix = f"/{api_target}"

        # explicit routes for UI with full route prefix
        proxy_router.add("http://localhost:10002", f"run/{os.environ['GIGANTUM_CLIENT_ID']}")
    else:
        api_target = "api"

    proxy_router.add("http://localhost:10001", api_target)
    logger.info(f"Proxy routes ({type(proxy_router)}): {proxy_router.routes}")

    return api_prefix


def configure_default_server(config_instance: Configuration) -> None:
    """Function to check if a server has been configured, and if not, configure and select the default server"""
    try:
        # Load the server configuration. If you get a FileNotFoundError there is no configured server
        config_instance.get_server_configuration()
    except FileNotFoundError:
        default_server = config_instance.config['core']['default_server']
        logger.info(f"Configuring Client with default server via auto-discovery: {default_server}")
        try:
            server_id = config_instance.add_server(default_server)
            config_instance.set_current_server(server_id)

            # Migrate any user dirs if needed. Here we assume all projects belong to the default server, since
            # at the time it was the only available server.
            migrate_work_dir_structure_v2(server_id)
        except Exception as err:
            logger.exception(f"Failed to configure default server! Restart Client to try again: {err}")
            # Re-raise the exception so the API doesn't come up
            raise


# Start Flask Server Initialization and app configuration
app = Flask("lmsrvlabbook")

random_bytes = os.urandom(32)
app.config["SECRET_KEY"] = base64.b64encode(random_bytes).decode('utf-8')
app.config["LABMGR_CONFIG"] = config = Configuration(wait_for_cache=10)
configure_default_server(config)
app.config["ID_MGR_CLS"] = get_identity_manager_class(config)

# Set Debug mode
app.config['DEBUG'] = config.config["flask"]["DEBUG"]
app.register_blueprint(blueprint.complete_labbook_service)

# Set starting flags
# If flask is run in debug mode the service will restart when code is changed, and some tasks
#   we only want to happen once (ON_FIRST_START)
# The WERKZEUG_RUN_MAIN environmental variable is set only when running under debugging mode
ON_FIRST_START = app.config['DEBUG'] is False or os.environ.get('WERKZEUG_RUN_MAIN') != 'true'
ON_RESTART = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

if os.environ.get('CIRCLECI') == 'true':
    try:
        url_prefix = configure_chp(config.config['proxy'], config.is_hub_client)
    except requests.exceptions.ConnectionError:
        url_prefix = config.config['proxy']["labmanager_api_prefix"]
else:
    url_prefix = configure_chp(config.config['proxy'], config.is_hub_client)

# Add rest routes
app.register_blueprint(rest_routes.rest_routes, url_prefix=url_prefix)


if config.config["flask"]["allow_cors"]:
    # Allow CORS
    CORS(app, max_age=7200)

if ON_FIRST_START:
    # Empty container-container share dir as it is ephemeral
    share_dir = os.path.join(os.path.sep, 'mnt', 'share')
    logger.info("Emptying container-container share folder: {}.".format(share_dir))
    try:
        for item in os.listdir(share_dir):
            item_path = os.path.join(share_dir, item)
            if os.path.isfile(item_path):
                os.unlink(item_path)
            else:
                shutil.rmtree(item_path)
    except Exception as e:
        logger.error(f"Failed to empty share folder: {e}.")
        raise

    post_save_hook_code = """
import subprocess, os
def post_save_hook(os_path, model, contents_manager, **kwargs):
    try:
        client_ip = os.environ.get('GIGANTUM_CLIENT_IP')
        if os.environ.get('HUB_CLIENT_ID'):
            # Running in the Hub
            service_route = "run/{}/api/savehook".format(os.environ.get('HUB_CLIENT_ID'))
        else:
            # Running locally
            service_route = "api/savehook"

        tokens = open('/home/giguser/jupyter_token').read().strip()
        username, owner, lbname, jupyter_token = tokens.split(',')
        url_args = "file={}&jupyter_token={}&email={}".format(os.path.basename(os_path), jupyter_token, os.environ['GIGANTUM_EMAIL'])
        url = "http://{}:10001/{}/{}/{}/{}?{}".format(client_ip,service_route,username,owner,lbname,url_args)
        subprocess.run(['wget', '--spider', url], cwd='/tmp')
    except Exception as e:
        print(e)

"""
    os.makedirs(os.path.join(share_dir, 'jupyterhooks'))
    with open(os.path.join(share_dir, 'jupyterhooks', '__init__.py'), 'w') as initpy:
        initpy.write(post_save_hook_code)

    # Reset distributed lock, if desired
    if config.config["lock"]["reset_on_start"]:
        logger.info("Resetting ALL distributed locks")
        reset_all_locks(config.config['lock'])

    # Create local data (for local dataset types) dir if it doesn't exist
    local_data_dir = os.path.join(config.config['git']['working_directory'], 'local_data')
    if os.path.isdir(local_data_dir) is False:
        os.makedirs(local_data_dir, exist_ok=True)
        logger.info(f'Created `local_data` dir for Local Filesystem Dataset Type: {local_data_dir}')

    # Create certificates file directory for custom CA certificate support.
    certificate_dir = os.path.join(config.config['git']['working_directory'], 'certificates')
    if os.path.isdir(certificate_dir) is False:
        os.makedirs(certificate_dir, exist_ok=True)
        logger.info(f'Created `certificates` dir for custom CA certificates: {certificate_dir}')

    # make sure temporary upload directory exists and is empty
    tempdir = config.upload_dir
    if os.path.exists(tempdir):
        shutil.rmtree(tempdir)
        logger.info(f'Cleared upload temp dir: {tempdir}')
    os.makedirs(tempdir)

    # Start background startup tasks
    d = Dispatcher()
    # Make sure the queue is up before we start using RQ
    for _ in range(20):
        if d.ready_for_job(update_environment_repositories):
            break
        sleep(0.5)
    else:
        # We exhausted our for-loop
        err_message = "Worker queue not ready after 20 tries (10 seconds) - fatal error"
        logger.error(err_message)
        raise RuntimeError(err_message)

    # Run job to update Base images in the background
    d.dispatch_task(update_environment_repositories, persist=True)


# Set auth error handler
@app.errorhandler(AuthenticationError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response


# TEMPORARY KLUDGE
# Due to GitPython implementation, resources leak. This block deletes all GitPython instances at the end of the request
# Future work will remove GitPython, at which point this block should be removed.
@app.after_request
def cleanup_git(response):
    loader = getattr(flask.request, 'labbook_loader', None)
    if loader:
        for key in loader.__dict__["_promise_cache"]:
            try:
                lb = loader.__dict__["_promise_cache"][key].value
                lb.git.repo.__del__()
            except AttributeError:
                continue
    return response
# TEMPORARY KLUDGE


def main(debug=False) -> None:
    try:
        # Run app on 0.0.0.0, assuming not an issue since it should be in a container
        # Please note: Debug mode must explicitly be set to False when running integration
        # tests, due to properties of Flask werkzeug dynamic package reloading.
        if debug:
            # This is to support integration tests, which will call main
            # with debug=False in order to avoid runtime reloading of Python code
            # which causes the interpreter to crash.
            app.run(host="0.0.0.0", port=10001, debug=debug)
        else:
            # If debug arg is not explicitly given then it is loaded from config
            app.run(host="0.0.0.0", port=10001)
    except Exception as err:
        logger.exception(err)
        raise


if __name__ == '__main__':
    main()
