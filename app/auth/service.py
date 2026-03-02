"""Authentication service with JWT and MongoDB user management"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from pymongo import MongoClient
import logging

from app.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Handles user authentication, JWT tokens, and user CRUD"""

    def __init__(self):
        self.client = MongoClient(settings.mongodb_uri)
        self.db = self.client[settings.mongodb_db_name]
        self.users = self.db["users"]

        # Ensure unique indexes
        self.users.create_index("username", unique=True)
        self.users.create_index("email", unique=True)

        logger.info("AuthService initialized")

    # -- password helpers --
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    # -- user CRUD --
    def create_user(self, username: str, email: str, password: str) -> Dict[str, Any]:
        now = datetime.utcnow()
        doc = {
            "username": username,
            "email": email,
            "hashed_password": self.hash_password(password),
            "created_at": now,
            "updated_at": now,
        }
        self.users.insert_one(doc)
        logger.info(f"Created user: {username}")
        return {"username": username, "email": email, "created_at": now}

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        return self.users.find_one({"username": username})

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return self.users.find_one({"email": email})

    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        user = self.get_user_by_username(username)
        if not user:
            return None
        if not self.verify_password(password, user["hashed_password"]):
            return None
        return user

    # -- JWT helpers --
    def create_access_token(self, username: str) -> str:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        payload = {"sub": username, "exp": expire, "type": "access"}
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    def create_refresh_token(self, username: str) -> str:
        expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
        payload = {"sub": username, "exp": expire, "type": "refresh"}
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    def verify_token(self, token: str, expected_type: str = "access") -> Optional[str]:
        """Verify a JWT token and return the username, or None on failure."""
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            if payload.get("type") != expected_type:
                return None
            return payload.get("sub")
        except JWTError:
            return None

    def close(self):
        if self.client:
            self.client.close()
            logger.info("AuthService MongoDB connection closed")


# Singleton
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
