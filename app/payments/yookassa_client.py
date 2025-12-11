import hashlib
import hmac
import base64
import os


def verify_yookassa_signature(request_body: bytes, received_signature: str) -> bool:
    secret = os.getenv("YOOKASSA_SECRET_KEY").encode()
    digest = hmac.new(secret, request_body, hashlib.sha256).digest()
    computed_signature = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed_signature, received_signature)
