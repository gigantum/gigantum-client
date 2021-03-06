import redis
import datetime
from abc import ABC, abstractmethod
from typing import Tuple, Optional

from gtmcore.logging import LMLogger
from gtmcore.inventory.inventory import InventoryManager

logger = LMLogger.get_logger()


class RepoCacheEntry(ABC):
    """ Represents a specific entry in the cache for a specific Repository """
    def __init__(self, redis_conn: redis.StrictRedis, key: str):
        self.db = redis_conn
        self.key = key

    def __str__(self):
        return f"RepoCacheEntry({self.key})"

    @staticmethod
    def _extract_id(key_value: str) -> Tuple[str, str, str]:
        token, user, owner, name = key_value.rsplit('&', 3)
        return user, owner, name

    @abstractmethod
    def _load_repo(self) -> Tuple[datetime.datetime, datetime.datetime, str]:
        """This contains methods for retrieving description, modified time, and created time."""
        raise NotImplemented

    def fetch_cachable_fields(self) -> Tuple[datetime.datetime, datetime.datetime, str]:
        logger.debug(f"Fetching {self.key} fields from disk.")
        self.clear()
        create_ts, modify_ts, description = self._load_repo()
        self.db.hset(self.key, 'description', description)
        self.db.hset(self.key, 'creation_date', create_ts.strftime("%Y-%m-%dT%H:%M:%S.%f"))
        self.db.hset(self.key, 'modified_on', modify_ts.strftime("%Y-%m-%dT%H:%M:%S.%f"))
        return create_ts, modify_ts, description

    @staticmethod
    def _date(bin_str: bytes) -> Optional[datetime.datetime]:
        """Return a datetime instance from byte-string, but return None if input is None"""
        if bin_str is None:
            return None
        date = datetime.datetime.strptime(bin_str.decode(), "%Y-%m-%dT%H:%M:%S.%f")
        return date.replace(tzinfo=datetime.timezone.utc)

    def _fetch_property(self, hash_field: str) -> bytes:
        """Retrieve all cache-able fields from the given repo"""
        val = self.db.hget(self.key, hash_field)
        if val is None:
            self.fetch_cachable_fields()
            val = self.db.hget(self.key, hash_field)

        return val

    @property
    def modified_on(self) -> datetime.datetime:
        d = self._date(self._fetch_property('modified_on'))
        if d is None:
            raise ValueError("Cannot retrieve modified_on")
        else:
            return d

    @property
    def created_time(self) -> datetime.datetime:
        d = self._date(self._fetch_property('creation_date'))
        if d is None:
            raise ValueError("Cannot retrieve creation_date")
        else:
            return d

    @property
    def description(self) -> str:
        return self._fetch_property('description').decode()

    def clear(self):
        """Remove this entry from the Redis cache. """
        logger.debug(f"Flushing cache entry for {self}")
        self.db.delete(self.key)


class LabbookCacheEntry(RepoCacheEntry):
    def _load_repo(self) -> Tuple[datetime.datetime, datetime.datetime, str]:
        lb = InventoryManager().load_labbook(*self._extract_id(self.key))
        return lb.creation_date, lb.modified_on, lb.description


class DatasetCacheEntry(RepoCacheEntry):
    def _load_repo(self) -> Tuple[datetime.datetime, datetime.datetime, str]:
        ds = InventoryManager().load_dataset(*self._extract_id(self.key))
        return ds.creation_date, ds.modified_on, ds.description


class RepoCacheController(ABC):
    """
    This class represents an interface to the cache that stores specific
    repository fields (modified time, created time, description). The
    `cached_*` methods retrieve the given fields, and insert it into the cache
    if needed to be re-fetched.
    """
    def __init__(self, cache_token: str, cache_entry_type):
        """ Note: Intended to be a PRIVATE constructor"""
        self.db = redis.StrictRedis(db=7)
        self.cache_token = cache_token
        self.cache_entry_type = cache_entry_type

    def _make_key(self, id_tuple: Tuple[str, str, str]) -> str:
        return '&'.join([self.cache_token, *id_tuple])

    def cached_modified_on(self, id_tuple: Tuple[str, str, str]) -> datetime.datetime:
        """ Retrieves the "modified_on" field of the given repository identified by `id_tuple`
        Args:
            id_tuple: Fields needed to uniqely identify this repository
        Returns:
            modified_on field, from cache if possible
        """
        return self.cache_entry_type(self.db, self._make_key(id_tuple)).modified_on

    def cached_created_time(self, id_tuple: Tuple[str, str, str]) -> datetime.datetime:
        """ Retrieves the "created_time" field of the given repository identified by `id_tuple`
        Args:
            id_tuple: Fields needed to uniqely identify this repository
        Returns:
            modified_on field, from cache if possible
        """
        return self.cache_entry_type(self.db, self._make_key(id_tuple)).created_time

    def cached_description(self, id_tuple: Tuple[str, str, str]) -> str:
        """ Retrieves the description field of the given repository identified by `id_tuple`
        Args:
            id_tuple: Fields needed to uniqely identify this repository
        Returns:
            description field, from cache if possible
        """
        return self.cache_entry_type(self.db, self._make_key(id_tuple)).description

    def clear_entry(self, id_tuple: Tuple[str, str, str]) -> None:
        """ Flush this entry from the cache - ie indicate it is stale """
        self.cache_entry_type(self.db, self._make_key(id_tuple)).clear()

    def clear_all(self):
        self.db.flushdb()


class LabbookCacheController(RepoCacheController):
    """Cache-manager for Labbooks"""
    def __init__(self):
        super().__init__('LABBOOK_CACHE', LabbookCacheEntry)


class DatasetCacheController(RepoCacheController):
    """Cache-manager for Datasets"""
    def __init__(self):
        super().__init__('DATASET_CACHE', DatasetCacheEntry)
