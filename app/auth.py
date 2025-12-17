from datetime import datetime, timedelta
from jose import jwt
import uuid
import redis
import os

SECRET_KEY = os.getenv("JWT_SECRET", "supersecret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Redis client (para refresh tokens)
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=6379,
    decode_responses=True
)

def create_refresh_token(user: str):
    token = str(uuid.uuid4())
    redis_client.setex(
        f"refresh:{token}",
        86400,   # 1 día
        user
    )
    return token

