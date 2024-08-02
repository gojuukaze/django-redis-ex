import re
import redis
from django.core.cache.backends.redis import RedisCache, RedisCacheClient, RedisSerializer
from django.utils.module_loading import import_string


class RedisEXCacheClient(RedisCacheClient):
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


class RedisEXCache(RedisCache):
    def __init__(self, server, params):
        super(RedisCache, self).__init__(params)
        if isinstance(server, str):
            self._servers = re.split("[;,]", server)
        else:
            self._servers = server

        self._class = RedisEXCacheClient
        self._options = params.get("OPTIONS", {})
