from typing import List, Dict
import json
from gtmcore.http import ConcurrentRequestManager, ConcurrentRequest

from gtmcore.environment.packagemanager import PackageManager, PackageResult, PackageMetadata
from gtmcore.container import container_for_context
from gtmcore.labbook import LabBook
from gtmcore.logging import LMLogger

logger = LMLogger.get_logger()


class CondaPackageManagerBase(PackageManager):
    """Class to implement the conda package manager
    """
    def __init__(self):
        # String to be set in child classes indicating which python version you are checking. Typically should be either
        # python 3.6* or python 2.7*
        self.python_depends_str = None

        # String of the name of the conda environment (e.g. py36 or py27, as created via container build)
        self.python_env = None

        # Note, currently we hard code channel config. Future changes to support the user specifying channels
        # will modify this behavior
        self.channel_priority = ['conda-forge', 'anaconda']
        self.request_mgr = ConcurrentRequestManager()

    def list_versions(self, package_name: str, labbook: LabBook, username: str) -> List[str]:
        """Method to list all available versions of a package based on the package name

        Args:
            package_name: Name of the package to query
            labbook: Subject LabBook
            username: username of current user

        Returns:
            list(str): Version strings
        """
        # Check for package in channels, picking out version by priority
        request_list = list()
        for channel in self.channel_priority:
            request_list.append(ConcurrentRequest(f"https://api.anaconda.org/package/{channel}/{package_name}",
                                                  headers={'Accept': 'application/json'}))

        responses = self.request_mgr.resolve_many(request_list)

        versions = None
        for response in responses:
            if response.status_code != 200:
                continue

            versions = response.json.get('versions')
            break

        if not versions:
            raise ValueError(f"Package {package_name} not found in channels {' ,'.join(self.channel_priority)}.")

        versions.reverse()
        return versions

    def list_installed_packages(self, labbook: LabBook, username: str) -> List[Dict[str, str]]:
        """Method to get a list of all packages that are currently installed

        Note, this will return results for the computer/container in which it is executed. To get the properties of
        a LabBook container, a docker exec command would be needed from the Gigantum application container.

        return format is a list of dicts with the format (name: <package name>, version: <version string>)

        Returns:
            list
        """
        project_container = container_for_context(username, labbook=labbook)
        result = project_container.run_container("conda list --no-pip --json", wait_for_output=True)
        if result:
            data = json.loads(result)

        if data:
            return [{"name": x['name'], 'version': x['version']} for x in data]
        else:
            return []

    def validate_packages(self, package_list: List[Dict[str, str]], labbook: LabBook, username: str) \
            -> List[PackageResult]:
        """Method to validate a list of packages, and if needed fill in any missing versions

        Should check both the provided package name and version. If the version is omitted, it should be generated
        from the latest version.

        Args:
            package_list(list): A list of dictionaries of packages to validate
            labbook(str): The labbook instance
            username(str): The username for the logged in user

        Returns:
            namedtuple: namedtuple indicating if the package and version are valid
        """
        result = list()

        # Check for package in channels, picking out version by priority
        request_list = list()
        for pkg in package_list:
            for channel in self.channel_priority:
                request_list.append(ConcurrentRequest(f"https://api.anaconda.org/package/{channel}/{pkg['package']}",
                                                      headers={'Accept': 'application/json'}))

        responses = self.request_mgr.resolve_many(request_list)

        # Repack into groups by package
        responses_per_package = list(zip(*(iter(responses),) * len(self.channel_priority)))

        for package, responses in zip(package_list, responses_per_package):
            versions = None
            latest_version = None
            for response in responses:
                if response.status_code != 200:
                    continue
                versions = response.json.get('versions')
                latest_version = response.json.get('latest_version')
                break

            if not versions:
                # Package is not found
                result.append(PackageResult(package=package['package'], version=package.get('version'), error=True))
                continue

            if package.get('version'):
                # Package has been set, so validate it
                if package.get('version') in versions:
                    # Both package name and version are valid
                    result.append(PackageResult(package=package['package'], version=package.get('version'),
                                                error=False))

                else:
                    # The package version is not in the list, so invalid
                    result.append(PackageResult(package=package['package'], version=package.get('version'), error=True))

            else:
                # You need to look up the latest version since not included
                result.append(PackageResult(package=package['package'], version=str(latest_version),
                                            error=False))

        return result

    def get_packages_metadata(self, package_list: List[str], labbook: LabBook, username: str) -> List[PackageMetadata]:
        """Method to get package metadata

        Args:
            package_list: List of package names
            labbook(str): The labbook instance
            username(str): The username for the logged in user

        Returns:
            list
        """
        def _extract_metadata(data):
            """Extraction method to pull out the docs URL and description"""
            latest_val = data.get('latest_version')
            description_val = data.get('summary').strip()

            docs_val = data.get('doc_url')
            if not docs_val:
                docs_val = data.get('html_url')

            return latest_val, description_val, docs_val

        # Check for package in channels, picking out version by priority
        request_list = list()
        for pkg in package_list:
            for channel in self.channel_priority:
                request_list.append(ConcurrentRequest(f"https://api.anaconda.org/package/{channel}/{pkg}",
                                                      headers={'Accept': 'application/json'},
                                                      extraction_function=_extract_metadata))
        responses = self.request_mgr.resolve_many(request_list)

        # Repack into groups by package
        responses_per_package = list(zip(*(iter(responses),) * len(self.channel_priority)))

        result = list()
        for package, responses in zip(package_list, responses_per_package):
            data = None
            for response in responses:
                if response.status_code == 200:
                    data = response.extracted_json
                    break

            if data:
                latest_version, description, docs_url = data
                result.append(PackageMetadata(package_manager="conda", package=package, latest_version=latest_version,
                                              description=description, docs_url=docs_url))
            else:
                result.append(PackageMetadata(package_manager="conda", package=package, latest_version=None,
                                              description=None, docs_url=None))

        return result

    def generate_docker_install_snippet(self, packages: List[Dict[str, str]], single_line: bool = False) -> List[str]:
        """Method to generate a docker snippet to install 1 or more packages

        Note: Because conda be so slow to solve environments with conda-forge included, always single line it.

        Args:
            packages(list(dict)): A list of package names and versions to install
            single_line(bool): If true, collapse

        Returns:
            list
        """
        package_strings = [f"{x['name']}={x['version']}" for x in packages]

        if single_line:
            return [f"RUN conda install -yq {' '.join(package_strings)}"]
        else:
            return [f"RUN conda install -yq {' '.join(package_strings)}"]


class Conda3PackageManager(CondaPackageManagerBase):
    """Class to implement the conda3 package manager
    """

    def __init__(self):
        super().__init__()
        self.python_depends_str = 'python 3.6*'
        self.python_env = 'py36'


class Conda2PackageManager(CondaPackageManagerBase):
    """Class to implement the conda2 package manager
    """

    def __init__(self):
        super().__init__()
        self.python_depends_str = 'python 2.7*'
        self.python_env = 'py27'
