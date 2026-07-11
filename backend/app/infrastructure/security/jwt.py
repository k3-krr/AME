import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict
import logging

from app.config import settings

logger = logging.getLogger("ame_backend.jwt")

ALGORITHM = "HS256"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a cryptographically signed JWT token.
    
    Args:
        data: The dictionary of claims to include in the payload.
        expires_delta: Optional duration before token expires.
        
    Returns:
        The encoded token as a string.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESSO_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates a JWT token signature and expiration.
    
    Args:
        token: The signed token string.
        
    Returns:
        The decoded dictionary payload if valid, otherwise None.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]}
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token verification failed: Signature expired.")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token verification failed: Invalid token - {e}")
        return None
