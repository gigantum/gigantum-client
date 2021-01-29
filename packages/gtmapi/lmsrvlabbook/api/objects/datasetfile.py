import graphene

from gtmcore.dataset import Manifest

from lmsrvcore.api.interfaces import GitRepository
from lmsrvcore.auth.user import get_logged_in_username


class DatasetFile(graphene.ObjectType):
    """A type representing a file or directory inside the dataset file system."""
    class Meta:
        interfaces = (graphene.relay.Node, GitRepository)

    # Loaded file info
    _file_info = None

    # Relative path from labbook section.
    key = graphene.String(required=True)

    # True indicates that path points to a directory
    is_dir = graphene.Boolean()

    # True indicates that the file has been downloaded and exists locally
    is_local = graphene.Boolean()

    # Modified at contains timestamp of last modified - NOT creation - in epoch time with nanosecond resolution if
    # supported by the underlying filesystem of the host
    modified_at = graphene.Float()

    # Size in bytes encoded as a string.
    size = graphene.String()

    def _load_file_info(self, dataloader):
        """Private method to retrieve file info for a given key"""
        if not self._file_info:
            # Load file info from LabBook
            if not self.key:
                raise ValueError("Must set `key` on object creation to resolve file info")

            # Load dataset instance
            username = get_logged_in_username()
            ds = dataloader.load(f"{username}&{self.owner}&{self.name}").get()

            manifest = Manifest(ds, username)

            # Retrieve file info
            self._file_info = manifest.get(self.key)

        # Set class properties
        self.is_dir = self._file_info['is_dir']
        self.modified_at = self._file_info['modified_at']
        self.size = f"{self._file_info['size']}"
        self.is_local = self._file_info['is_local']

    @classmethod
    def get_node(cls, info, id):
        """Method to resolve the object based on it's Node ID"""
        # Parse the key
        owner, name, key = id.split("&")

        return DatasetFile(id=f"{owner}&{name}&{key}", name=name, owner=owner, key=key)

    def resolve_id(self, info):
        """Resolve the unique Node id for this object"""
        if not self.id:
            if not self.owner or not self.name or not self.key:
                raise ValueError("Resolving a DatasetFile Node ID requires owner, name, and key to be set")
            self.id = f"{self.owner}&{self.name}&{self.key}"

        return self.id

    def resolve_is_dir(self, info):
        """Resolve the is_dir field"""
        if self.is_dir is None:
            self._load_file_info(info.context.dataset_loader)
        return self.is_dir

    def resolve_modified_at(self, info):
        """Resolve the modified_at field"""
        if self.modified_at is None:
            self._load_file_info(info.context.dataset_loader)
        return self.modified_at

    def resolve_size(self, info):
        """Resolve the size field"""
        if self.size is None:
            self._load_file_info(info.context.dataset_loader)
        return self.size

    def resolve_is_local(self, info):
        """Resolve the is_local field"""
        if self.is_local is None:
            self._load_file_info(info.context.dataset_loader)
        return self.is_local
