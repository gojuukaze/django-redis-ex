# django-redis-ex

该库基于 `django.core.cache.backends.redis.RedisCache` 修改。 

它使用 asyncio Redis 创建连接，支持异步和同步两种方法。
还修复了 Django RedisCache 的连接池bug（[#35651](https://code.djangoproject.com/ticket/35651)）。

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
配置参数说明请参阅官方文档。
* https://docs.djangoproject.com/en/5.0/topics/cache/#redis
* https://docs.djangoproject.com/en/5.0/topics/cache/#cache-arguments


您也可以使用修复了bug的同步cache 。

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis_ex.cache.RedisEXCache",
        "LOCATION": "redis://127.0.0.1:6379",
    }
}
```

## Notes
虽然`RedisEXCache`、`AsyncRedisEXCache` 同时支持异步和同步方法，但建议在同步项目中使用`RedisEXCache`，异步项目中使用`AsyncRedisEXCache`。

如果你的项目同时包含同步和异步的代码，建议添加两个cache（一个同步、一个异步）。
比如：
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

## Session

由于 Django 的session还不支持异步，如果使用缓存作为session后端，建议添加个同步缓存并将其设置为session后端。
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

# Raw client
`AsyncRedisEXCache`的同步方法会在使用后关闭连接，如果你需要在同步函数中使用`AsyncRedisEXCache` 的raw client，你同样需要在使用后关闭连接。

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
