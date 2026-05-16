import base64
import hashlib
import hmac
import json
import os
import time


SESSION_SECRET = os.getenv(
    "EDUQUEST_SESSION_SECRET",
    "eduquest-local-defense-secret",
).encode("utf-8")
SESSION_TTL_SECONDS = int(os.getenv("EDUQUEST_SESSION_TTL_SECONDS", "43200"))


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(f"{encoded}{padding}".encode("ascii"))


def create_session_token(user_id: int, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    }
    payload_segment = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"),
    )
    signature_segment = _b64encode(
        hmac.new(
            SESSION_SECRET,
            payload_segment.encode("utf-8"),
            hashlib.sha256,
        ).digest(),
    )
    return f"{payload_segment}.{signature_segment}"


def verify_session_token(token: str) -> dict:
    try:
        payload_segment, signature_segment = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid session token format") from exc

    expected_signature = _b64encode(
        hmac.new(
            SESSION_SECRET,
            payload_segment.encode("utf-8"),
            hashlib.sha256,
        ).digest(),
    )
    if not hmac.compare_digest(signature_segment, expected_signature):
        raise ValueError("Invalid session token signature")

    try:
        payload = json.loads(_b64decode(payload_segment).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Invalid session token payload") from exc

    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("Session token expired")

    sub = payload.get("sub")
    if not isinstance(sub, int):
        raise ValueError("Invalid session token subject")
    return payload
