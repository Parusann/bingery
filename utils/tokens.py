"""Helpers for generating URL-safe random tokens."""
import secrets


def generate_share_token(length: int = 16) -> str:
    """Return a URL-safe random token of roughly `length` characters."""
    return secrets.token_urlsafe(length)[:length]
