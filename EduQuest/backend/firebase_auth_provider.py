from dataclasses import dataclass
from pathlib import Path
import os

from firebase_admin import auth, credentials, get_app, initialize_app


class FirebaseConfigurationError(RuntimeError):
    pass


class FirebaseVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class FirebaseIdentity:
    uid: str
    email: str
    full_name: str | None = None


_DEFAULT_SERVICE_ACCOUNT = (
    Path(__file__).resolve().parents[1]
    / "dimploma-c484d-firebase-adminsdk-fbsvc-079c0dd796.json"
)


def _service_account_path() -> Path:
    configured = os.getenv("FIREBASE_ADMIN_CREDENTIALS")
    if configured:
        return Path(configured).expanduser().resolve()
    return _DEFAULT_SERVICE_ACCOUNT


def _firebase_app():
    try:
        return get_app()
    except ValueError:
        credential_path = _service_account_path()
        if not credential_path.exists():
            raise FirebaseConfigurationError(
                f"Firebase Admin credentials not found at {credential_path}"
            )
        try:
            certificate = credentials.Certificate(str(credential_path))
            return initialize_app(certificate)
        except Exception as exc:  # pragma: no cover - SDK-specific failures
            raise FirebaseConfigurationError(
                f"Unable to initialize Firebase Admin SDK: {exc}"
            ) from exc


def verify_firebase_bearer_token(token: str) -> FirebaseIdentity:
    if not token:
        raise FirebaseVerificationError("Firebase bearer token missing")

    app = _firebase_app()
    try:
        payload = auth.verify_id_token(token, app=app)
    except FirebaseConfigurationError:
        raise
    except Exception as exc:  # pragma: no cover - SDK-specific failures
        raise FirebaseVerificationError("Invalid Firebase bearer token") from exc

    uid = payload.get("uid") or payload.get("user_id") or payload.get("sub")
    email = payload.get("email")
    if not isinstance(uid, str) or not uid.strip():
        raise FirebaseVerificationError("Firebase token missing uid")
    if not isinstance(email, str) or not email.strip():
        raise FirebaseVerificationError("Firebase token missing email")

    name = payload.get("name")
    return FirebaseIdentity(
        uid=uid.strip(),
        email=email.strip().lower(),
        full_name=name.strip() if isinstance(name, str) and name.strip() else None,
    )
