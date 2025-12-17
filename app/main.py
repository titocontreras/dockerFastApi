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
from fastapi import HTTPException
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer

from limiter import limiter
from auth import create_access_token

from jose import jwt, JWTError
from auth import SECRET_KEY, ALGORITHM


from auth import create_access_token
from fastapi import HTTPException


app = FastAPI()

@app.middleware("http")
async def attach_user_from_jwt(request, call_next):
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            request.state.user = payload.get("sub")
        except:
            request.state.user = None
    response = await call_next(request)
    return response


from fastapi import WebSocket, WebSocketDisconnect



#PROTECCION DE WEB SOCKET INICIO
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")

    if not token:
        await ws.close(code=1008)
        return

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = payload.get("sub")
    except:
        await ws.close(code=1008)
        return

    await ws.accept()

    try:
        while True:
            data = await ws.receive_text()
            await ws.send_text(f"{user}: {data}")
    except WebSocketDisconnect:
        print(f"{user} disconnected")

#PROTECCION DE WEB SOCKET INICIOFIN

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


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
@limiter.limit("100/minute")
async def list_users(
    user=Depends(get_current_user),
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
async def login(username: str):
    access_token = create_access_token({"sub": username})
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@app.get("/profile")
@limiter.limit("60/minute")
async def profile(user=Depends(get_current_user)):
    return {"user": user}


@app.post("/refresh")
async def refresh(refresh_token: str):
    user = redis_client.get(f"refresh:{refresh_token}")

    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = create_access_token({"sub": user})
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@app.post("/logout")
async def logout(refresh_token: str):
    redis_client.delete(f"refresh:{refresh_token}")
    return {"detail": "Logged out"}
