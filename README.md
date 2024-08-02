# django-redis-ex

This library is based on `django.core.cache.backends.redis.RedisCache` modification.

It uses asyncio Redis to create connections and both asynchronous and synchronous methods are supported.
Also fixed a connection pooling bug Django RedisCache ([#35651](https://code.djangoproject.com/ticket/35651)).

# User guide

## Installation

```shell
pip install django-redis-ex
```

## Configure as cache backend

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis_ex.async_cache.AsyncRedisEXCache",
        "LOCATION": "redis://127.0.0.1:6379",
    }
}
```

Refer to the official documentation for configuration parameter descriptions.

* https://docs.djangoproject.com/en/5.0/topics/cache/#redis
* https://docs.djangoproject.com/en/5.0/topics/cache/#cache-arguments

You can also use the bug-fixed synchronization cache.

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis_ex.cache.RedisEXCache",
        "LOCATION": "redis://127.0.0.1:6379",
    }
}
```

## Notes

Although `RedisEXCache`, `AsyncRedisEXCache` support both asynchronous and synchronous methods, it is recommended to
use `RedisEXCache` for synchronous projects and `AsyncRedisEXCache` for asynchronous projects.

If your project contains both synchronous and asynchronous code, it is recommended to add two caches (one synchronous
and one asynchronous).
For example:

```python

CACHES = {
    "default": {
        "BACKEND": "django_redis_ex.async_cache.AsyncRedisEXCache",
        "LOCATION": "redis://127.0.0.1:6379",
    },
    "sync_cache": {
        "BACKEND": "django_redis_ex.cache.RedisEXCache",
        "LOCATION": "redis://127.0.0.1:6379",
    },
}
```

```python
from django.core.cache import caches


def sync_do():
    caches['sync_cache'].get('key')


async def async_do():
    await caches['default'].aget('key')
```

## About Session

Since Django's session does not yet support asynchrony, if you are using a cache as a session backend, it is recommended
to add a synchronized cache and set it as the session backend.

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis_ex.async_cache.AsyncRedisEXCache",
        "LOCATION": "redis://127.0.0.1:6379",
    },
    "sync_cache": {
        "BACKEND": "django_redis_ex.cache.RedisEXCache",
        "LOCATION": "redis://127.0.0.1:6379",
    },
}

SESSION_CACHE_ALIAS = 'sync_cache'
```

# Raw client

The synchronization method of `AsyncRedisEXCache` closes the connection after use, and if you need to use the raw client
of `AsyncRedisEXCache` in a synchronization function, you likewise need to close the connection after use.

```python
from django.core.cache import cache
from asgiref.sync import async_to_sync


async def aget_data():
    client = cache._cache.get_client(write=False)
    a = await client.get("a")
    b = await client.get("b")
    await client.aclose(close_connection_pool=True)
    return a, b


def get_data():
    return async_to_sync(aget_data)()
```
