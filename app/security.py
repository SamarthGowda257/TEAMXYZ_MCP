"""Password hashing (scrypt) and signed, expiring session tokens (HMAC-SHA256). Stdlib only."""

import base64
import hashlib
import hmac
import json
import os
import time

from . import config


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def verify_password(pw: str, stored: str | None) -> bool:
    try:
        _, salt_b64, h_b64 = (stored or "").split("$")
        h = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt_b64), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(h, base64.b64decode(h_b64))
    except Exception:
        return False


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_token(payload: dict, ttl_seconds: int = 7 * 24 * 3600) -> str:
    body = dict(payload, exp=int(time.time()) + ttl_seconds)
    raw = _b64(json.dumps(body, separators=(",", ":")).encode())
    sig = _b64(hmac.new(config.SECRET_KEY.encode(), raw.encode(), hashlib.sha256).digest())
    return f"{raw}.{sig}"


def read_token(token: str) -> dict | None:
    try:
        raw, sig = token.split(".")
        good = _b64(hmac.new(config.SECRET_KEY.encode(), raw.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        body = json.loads(_unb64(raw))
        return body if body.get("exp", 0) > time.time() else None
    except Exception:
        return None


def token_matches(given: str | None, expected: str) -> bool:
    return bool(given) and bool(expected) and hmac.compare_digest(given.encode(), expected.encode())
