import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _derive_fernet_key() -> bytes:
    return base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )


def encrypt_value(plain_text: str) -> str:
    f = Fernet(_derive_fernet_key())
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_value(cipher_text: str) -> str:
    f = Fernet(_derive_fernet_key())
    return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
