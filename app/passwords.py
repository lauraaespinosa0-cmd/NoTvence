"""Hashing and verification for user passwords."""

import hmac

from argon2.exceptions import VerificationError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a password with the recommended Argon2id configuration."""
    return _password_hash.hash(password)


def verify_password_and_update(
    password: str, stored_password: str
) -> tuple[bool, str | None]:
    """Verify a password and return a replacement hash when needed.

    Plain-text values are accepted only to upgrade accounts created before
    password hashing was introduced.
    """
    if not isinstance(stored_password, str):
        return False, None

    if stored_password.startswith("$argon2"):
        try:
            return _password_hash.verify_and_update(password, stored_password)
        except (TypeError, ValueError, UnknownHashError, VerificationError):
            return False, None

    if hmac.compare_digest(password, stored_password):
        return True, hash_password(password)

    return False, None
