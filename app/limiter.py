from slowapi import Limiter
from slowapi.util import get_remote_address

def rate_limit_key(request):
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user}"
    return request.client.host

limiter = Limiter(key_func=rate_limit_key)
