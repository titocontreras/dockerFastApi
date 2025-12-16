import json
import redis
import os

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=6379,
    decode_responses=True
)

def get_cache(key: str):
    value = redis_client.get(key)
    if value:
        return json.loads(value)
    return None

def set_cache(key: str, data, ttl: int = 60):
    redis_client.setex(key, ttl, json.dumps(data))

def delete_cache(key: str):
    redis_client.delete(key)

