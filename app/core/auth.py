import logging
from typing import Dict, Any
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models.user import User

from app.core.config import settings

logger = logging.getLogger(__name__)

#Reusable HTTP transport for caching Google's public certificates
_google_request = google_requests.Request()

#Extracts 'Authorization: Bearer <token> from request headers
security = HTTPBearer()


def verify_firebase_token(token:str) -> Dict[str,Any]:
    """ Verifies a Firebase ID token using Google's public certificates.
        returns the decoded token claims ('user_id','email',etc.).
        Raises HTTPException(401) if invalid or expired.
    """

    if not settings.FIREBASE_PROJECT_ID:
        logger.warning("FIREBASE_PROJECT_ID not configured in settings");

    try:
        #verifies signature, expiry and audience against Google's public keys
        decoded_token = id_token.verify_firebase_token(
            token,
            _google_request,
            audience=settings.FIREBASE_PROJECT_ID
        )
        return decoded_token

    except ValueError as e:
        logger.warning("Firebase token verification failed: %s",e)
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authentication token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_token_claims(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str,Any]:
    """Validates the bearer token and returns decoded Firebase claims. User for user registration when the user doesn't exist in Postgres yet."""
    return verify_firebase_token(credentials.credentials)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db:AsyncSession = Depends(get_db)
) -> User:

    claims = verify_firebase_token(credentials.credentials)

    uid = claims.get("user_id") or claims.get("sub")
    if not uid:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Authentication does not contain a valid user_id",
            headers={"WWW-Authenticate": "Bearer"},
        )
    result = await db.execute(select(User).where(User.user_id == uid))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail = f"User profile with ID '{uid}' not found. Please register first."
        )

    return user

    