import os
import random
import re
import redis.asyncio as redis
from asgiref.sync import async_to_sync

from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache
from django.core.cache.backends.redis import RedisSerializer
from django.utils.functional import cached_property
from django.utils.module_loading import import_string


class AsyncRedisEXCacheClient:
    _pools = {}

    def __init__(self, servers, serializer=None, pool_class=None, parser_class=None, **options):

        self._lib = redis
        self._servers = servers

        # Can't initialize it here,
        # otherwise the pool will be reset when the cache is used.
        # self._pools = {}

        self._client = self._lib.Redis

        if isinstance(pool_class, str):
            pool_class = import_string(pool_class)
        self._pool_class = pool_class or self._lib.ConnectionPool

        if isinstance(serializer, str):
            serializer = import_string(serializer)
        if callable(serializer):
            serializer = serializer()
        self._serializer = serializer or RedisSerializer()

        if isinstance(parser_class, str):
            parser_class = import_string(parser_class)
        parser_class = parser_class or self._lib.connection.DefaultParser

        self._pool_options = {"parser_class": parser_class, **options}

    def _get_connection_pool_index(self, write):
        # Write to the first server. Read from other servers if there are more,
        # otherwise read from the first server.
        if write or len(self._servers) == 1:
            return 0
        return random.randint(1, len(self._servers) - 1)

    def _get_connection_pool(self, write):
        index = self._get_connection_pool_index(write)
        if index not in self._pools:
            self._pools[index] = self._pool_class.from_url(
                self._servers[index],
                **self._pool_options,
            )
        return self._pools[index]

    def get_client(self, key=None, *, write=False) -> redis.Redis:
        # key is used so that the method signature remains the same and custom
        # cache client can be implemented which might require the key to select
        # the server, e.g. sharding.
        pool = self._get_connection_pool(write)
        return self._client(connection_pool=pool)

    async def aadd(self, key, value, timeout, close=False):
        client = self.get_client(key, write=True)
        value = self._serializer.dumps(value)
        try:
            if timeout == 0:
                if ret := bool(client.set(key, value, nx=True)):
                    await client.delete(key)
                return ret
            else:
                return bool(await client.set(key, value, ex=timeout, nx=True))
        finally:
            if close:
                await client.aclose(close_connection_pool=True)

    def add(self, key, value, timeout):
        return async_to_sync(self.aadd)(key, value, timeout, True)

    async def aget(self, key, default, close=False):
        client = self.get_client(key)
        try:
            value = await client.get(key)
            return default if value is None else self._serializer.loads(value)
        finally:
            if close:
                await client.aclose(close_connection_pool=True)

    def get(self, key, default=None):
        return async_to_sync(self.aget)(key, default, True)

    async def aset(self, key, value, timeout, close=False):
        client = self.get_client(key, write=True)
        value = self._serializer.dumps(value)
        try:
            if timeout == 0:
                await client.delete(key)
            else:
                await client.set(key, value, ex=timeout)
        finally:
            if close:
                await client.aclose(close_connection_pool=True)

    def set(self, key, value, timeout):
        return async_to_sync(self.aset)(key, value, timeout, True)

    async def atouch(self, key, timeout, close=False):
        client = self.get_client(key, write=True)
        try:
            if timeout is None:
                return bool(await client.persist(key))
            else:
                return bool(await client.expire(key, timeout))
        finally:
            if close:
                await client.aclose(close_connection_pool=True)

    def touch(self, key, timeout):
        return async_to_sync(self.atouch)(key, timeout, True)

    async def adelete(self, key, close=False):
        client = self.get_client(key, write=True)
        try:
            return bool(await client.delete(key))
        finally:
            if close:
                await client.aclose(close_connection_pool=True)

    def delete(self, key):
        return async_to_sync(self.adelete)(key, True)

    async def aget_many(self, keys, close=False):
        client = self.get_client(None)
        try:
            ret = await client.mget(keys)
            return {
                k: self._serializer.loads(v) for k, v in zip(keys, ret) if v is not None
            }
        finally:
            if close:
                await client.aclose(close_connection_pool=True)

    def get_many(self, keys):
        return async_to_sync(self.aget_many)(keys, True)

    async def ahas_key(self, key, close=False):
        client = self.get_client(key)
        try:
            return bool(await client.exists(key))
        finally:
            if close:
                await client.aclose(close_connection_pool=True)

    def has_key(self, key):
        return async_to_sync(self.ahas_key)(key, True)

    async def aincr(self, key, delta, close=False):
        client = self.get_client(key, write=True)
        try:
            if not await client.exists(key):
                raise ValueError("Key '%s' not found." % key)
            return await client.incr(key, delta)
        finally:
            if close:
                await client.aclose(close_connection_pool=True)

    def incr(self, key, delta):
        return async_to_sync(self.aincr)(key, delta, True)

    async def aset_many(self, data, timeout, close=False):
        client = self.get_client(None, write=True)
        try:
            async with client.pipeline() as pipeline:
                await pipeline.mset({k: self._serializer.dumps(v) for k, v in data.items()})
                if timeout is not None:
                    # Setting timeout for each key as redis does not support timeout
                    # with mset().
                    for key in data:
                        await pipeline.expire(key, timeout)
                await pipeline.execute()
        finally:
            if close:
                await client.aclose(close_connection_pool=True)

    def set_many(self, data, timeout):
        return async_to_sync(self.aset_many)(data, timeout, True)

    async def adelete_many(self, keys, close=False):
        client = self.get_client(None, write=True)
        try:
            await client.delete(*keys)
        finally:
            if close:
                await client.aclose(close_connection_pool=True)

    def delete_many(self, keys):
        return async_to_sync(self.adelete_many)(keys, True)

    async def aclear(self, close=False):
        client = self.get_client(None, write=True)
        try:
            bool(await client.flushdb())
        finally:
            if close:
                await client.aclose(close_connection_pool=True)

    def clear(self):
        return async_to_sync(self.aclear)(True)


class AsyncRedisEXCache(BaseCache):
    def __init__(self, server, params):
        super().__init__(params)
        if isinstance(server, str):
            self._servers = re.split("[;,]", server)
        else:
            self._servers = server

        self._class = AsyncRedisEXCacheClient
        self._options = params.get("OPTIONS", {})

    @cached_property
    def _cache(self):
        return self._class(self._servers, **self._options)

    def get_backend_timeout(self, timeout=DEFAULT_TIMEOUT):
        if timeout == DEFAULT_TIMEOUT:
            timeout = self.default_timeout
        # The key will be made persistent if None used as a timeout.
        # Non-positive values will cause the key to be deleted.
        return None if timeout is None else max(0, int(timeout))

    async def aadd(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        return await self._cache.aadd(key, value, self.get_backend_timeout(timeout))

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.add(key, value, self.get_backend_timeout(timeout))

    async def aget(self, key, default=None, version=None):
        key = self.make_and_validate_key(key, version=version)
        return await self._cache.aget(key, default)

    def get(self, key, default=None, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.get(key, default)

    async def aset(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        return await self._cache.aset(key, value, self.get_backend_timeout(timeout))

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.set(key, value, self.get_backend_timeout(timeout))

    async def atouch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        return await self._cache.atouch(key, self.get_backend_timeout(timeout))

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.touch(key, self.get_backend_timeout(timeout))

    async def adelete(self, key, version=None):
        key = self.make_and_validate_key(key, version=version)
        return await self._cache.adelete(key)

    def delete(self, key, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.delete(key)

    async def aget_many(self, keys, version=None):
        key_map = {
            self.make_and_validate_key(key, version=version): key for key in keys
        }
        ret = await self._cache.aget_many(key_map.keys())
        return {key_map[k]: v for k, v in ret.items()}

    def get_many(self, keys, version=None):
        key_map = {
            self.make_and_validate_key(key, version=version): key for key in keys
        }
        ret = self._cache.get_many(key_map.keys())
        return {key_map[k]: v for k, v in ret.items()}

    async def ahas_key(self, key, version=None):
        key = self.make_and_validate_key(key, version=version)
        return await self._cache.ahas_key(key)

    def has_key(self, key, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.has_key(key)

    async def aincr(self, key, delta=1, version=None):
        key = self.make_and_validate_key(key, version=version)
        return await self._cache.aincr(key, delta)

    def incr(self, key, delta=1, version=None):
        key = self.make_and_validate_key(key, version=version)
        return self._cache.incr(key, delta)

    async def aset_many(self, data, timeout=DEFAULT_TIMEOUT, version=None):
        if not data:
            return []
        safe_data = {}
        for key, value in data.items():
            key = self.make_and_validate_key(key, version=version)
            safe_data[key] = value
        await self._cache.aset_many(safe_data, self.get_backend_timeout(timeout))
        return []

    def set_many(self, data, timeout=DEFAULT_TIMEOUT, version=None):
        if not data:
            return []
        safe_data = {}
        for key, value in data.items():
            key = self.make_and_validate_key(key, version=version)
            safe_data[key] = value
        self._cache.set_many(safe_data, self.get_backend_timeout(timeout))
        return []

    async def adelete_many(self, keys, version=None):
        if not keys:
            return
        safe_keys = [self.make_and_validate_key(key, version=version) for key in keys]
        await self._cache.adelete_many(safe_keys)

    def delete_many(self, keys, version=None):
        if not keys:
            return
        safe_keys = [self.make_and_validate_key(key, version=version) for key in keys]
        self._cache.delete_many(safe_keys)

    async def aclear(self):
        return await self._cache.aclear()

    def clear(self):
        return self._cache.clear()
