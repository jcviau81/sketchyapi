"""API key authentication."""

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from .config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthInfo:
    """Authenticated client info."""
    def __init__(self, api_key: str, tier: str):
        self.api_key = api_key
        self.tier = tier


async def require_auth(api_key: str = Security(api_key_header)) -> AuthInfo:
    """Validate API key and return auth info."""
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")

    keys = settings.parse_api_keys()

    # If no keys configured, allow all (dev mode)
    if not keys:
        return AuthInfo(api_key="dev", tier="pro")

    tier = keys.get(api_key)
    if tier is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")

    return AuthInfo(api_key=api_key, tier=tier)
