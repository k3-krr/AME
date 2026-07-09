from passlib.context import CryptContext

# Configure password context utilizing bcrypt hashing cycles
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Computes a cryptographically secure bcrypt hash of a raw text password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compares a plain text candidate against a secure bcrypt hash for equivalence."""
    return pwd_context.verify(plain_password, hashed_password)
