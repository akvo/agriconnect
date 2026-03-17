"""
Authentication dependency for Statistics API.

Provides token-based authentication for external applications
(e.g., Streamlit dashboards) to access statistics endpoints.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings

security = HTTPBearer()


async def verify_statistic_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> bool:
    """
    Verify the statistic API token.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        True if token is valid

    Raises:
        HTTPException: 503 if API not configured, 401 if invalid token
    """
    if not settings.statistic_api_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Statistics API not configured",
        )

    if credentials.credentials != settings.statistic_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True
