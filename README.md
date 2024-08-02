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

You can also use the bug-fixed synchronization `RedisEXCache`.

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis_ex.cache.RedisEXCache",
        "LOCATION": "redis://127.0.0.1:6379",
    }
}
```

## Notes
`RedisEXCache`, `AsyncRedisEXCache` supports both asynchronous and synchronous methods.  

However, the synchronization method in `AsyncRedisEXCache` will close the connection after use, so if your project has a lot of synchronization code using the cache, it is recommended that you add a synchronization cache and use it in your synchronization code.
for example:
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
Since Django's session does not yet support asynchrony, if you are using a cache as a session backend, it is recommended to add a synchronized cache and set it as the session backend.

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

SESSION_CACHE_ALIAS='sync_cache'
```