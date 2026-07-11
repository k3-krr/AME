import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import logging

from app.domain.repositories import IUserRepository, ISessionRepository
from app.infrastructure.db.models import UserTable, AuthSessionTable
from app.infrastructure.security.hashing import hash_password, verify_password
from app.infrastructure.security.jwt import create_access_token, decode_access_token

logger = logging.getLogger("ame_backend.auth_service")


def compute_token_hash(token: str) -> str:
    """Computes a SHA-256 hex hash of the token for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    """
    Application service managing authentication use cases: registration, login, logout,
    and session verification.
    """

    def __init__(self, user_repo: IUserRepository, session_repo: ISessionRepository):
        self.user_repo = user_repo
        self.session_repo = session_repo

    async def register_user(self, email: str, password: str) -> UserTable:
        """
        Registers a new user after verifying that the email does not exist.
        
        Args:
            email: Unique email address.
            password: Plaintext password.
            
        Returns:
            The newly created UserTable object.
            
        Raises:
            ValueError: If the email is already registered.
        """
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            raise ValueError("Email already registered")

        password_hash = hash_password(password)
        user = await self.user_repo.create(email=email, password_hash=password_hash)
        logger.info(f"Successfully registered user: {email} (ID: {user.id})")
        return user

    async def login_user(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[UserTable, str]:
        """
        Authenticates a user, starts a session in the database, and returns a signed JWT.
        
        Args:
            email: User's email.
            password: User's plaintext password.
            ip_address: Optional request IP address.
            user_agent: Optional request User Agent.
            
        Returns:
            A tuple of (UserTable, JWT token).
            
        Raises:
            ValueError: If credentials are invalid.
        """
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")

        # Generate session information
        session_id = uuid.uuid4()
        
        # Determine token lifetime
        from app.config import settings
        expires_delta = timedelta(minutes=settings.ACCESSO_TOKEN_EXPIRE_MINUTES)
        expires_at = datetime.now(timezone.utc) + expires_delta

        # Create JWT token
        token = create_access_token(
            data={"sub": str(user.id), "session_id": str(session_id)},
            expires_delta=expires_delta,
        )

        # Hash token for DB storage
        token_hash = compute_token_hash(token)

        # Create database session record
        await self.session_repo.create(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        logger.info(f"User logged in: {email} (Session ID: {session_id})")
        return user, token

    async def logout_user(self, token: str) -> bool:
        """
        Logs a user out by revoking the database session.
        
        Args:
            token: The raw JWT token string.
            
        Returns:
            True if the session was successfully deleted, otherwise False.
        """
        token_hash = compute_token_hash(token)
        deleted = await self.session_repo.delete_by_token(token_hash)
        if deleted:
            logger.info("Session successfully revoked.")
        else:
            logger.warning("Session revocation failed: token not found.")
        return deleted

    async def get_user_from_token(self, token: str) -> Optional[UserTable]:
        """
        Validates the JWT token, matches it against database sessions, and fetches the User.
        
        Args:
            token: The raw JWT token.
            
        Returns:
            The UserTable object if valid and active, otherwise None.
        """
        payload = decode_access_token(token)
        if not payload:
            return None

        # Verify that session exists and is active in the database
        token_hash = compute_token_hash(token)
        session = await self.session_repo.get_by_token(token_hash)
        if not session:
            logger.warning("JWT decoded successfully but database session not found (possibly logged out).")
            return None

        # Check session expiration
        now = datetime.now(timezone.utc)
        # Handle offset-naive and offset-aware datetimes
        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
            
        if now > expires_at:
            logger.warning("Database session has expired.")
            # Optionally clean up expired session
            await self.session_repo.delete_by_token(token_hash)
            return None

        # Fetch user
        user = await self.user_repo.get_by_id(session.user_id)
        return user
