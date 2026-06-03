import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path


SESSION_COOKIE = "astm_session"
SESSION_TTL_SECONDS = 12 * 60 * 60


def load_secret(data_dir: str) -> str:
    env_secret = os.getenv("SECRET_KEY")
    if env_secret:
        return env_secret

    path = Path(data_dir) / "secret.key"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()

    secret = secrets.token_urlsafe(48)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(secret, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return secret


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return "pbkdf2_sha256$210000$%s$%s" % (
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_session(username: str, secret: str) -> str:
    payload = {
        "username": username,
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(12),
    }
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), "sha256")
    return f"{payload_b64}.{signature.hexdigest()}"


def verify_session(cookie_value: str | None, secret: str) -> str | None:
    if not cookie_value or "." not in cookie_value:
        return None
    payload_b64, signature = cookie_value.rsplit(".", 1)
    expected = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), "sha256")
    if not hmac.compare_digest(signature, expected.hexdigest()):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")))
    except Exception:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return str(payload.get("username") or "") or None
