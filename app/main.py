from fastapi import FastAPI, Depends
import redis
import os
from sqlalchemy.ext.asyncio import AsyncSession

from database import engine, get_db
from models import Base, User
from cache import get_cache, set_cache, delete_cache

from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi.responses import JSONResponse
from limiter import limiter


app = FastAPI()

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=6379,
    decode_responses=True
)
#limiter 
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests"}
    )


# Crear tablas al iniciar
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def root():
    return {
        "status": "ok",
        "redis": redis_client.ping()
    }

@app.post("/users")
async def create_user(
    name: str,
    db: AsyncSession = Depends(get_db),
):
    user = User(name=name)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    delete_cache("users:list")  #  INVALIDA CACHE

    return user


@app.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
):
    cache_key = "users:list"

    cached = get_cache(cache_key)
    if cached:
        return cached

    result = await db.execute(User.__table__.select())
    users = result.mappings().all()

    set_cache(cache_key, users, ttl=30)
    return users

@app.post("/login")
@limiter.limit("5/minute")
async def login():
    return {"login": "ok"}
