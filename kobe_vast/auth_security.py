# -*- coding: utf-8 -*-
"""Password hashing, validation, and login security."""
import hashlib
import re
import secrets

MIN_PASSWORD_LEN = 8


def validate_password(password):
    """Return (ok, error_message_ar)."""
    p = (password or "").strip()
    if len(p) < MIN_PASSWORD_LEN:
        return False, f"كلمة المرور يجب أن تكون {MIN_PASSWORD_LEN} أحرف على الأقل"
    if not re.search(r"[A-Za-z\u0600-\u06FF]", p):
        return False, "كلمة المرور يجب أن تحتوي على حرف واحد على الأقل"
    if not re.search(r"\d", p):
        return False, "كلمة المرور يجب أن تحتوي على رقم واحد على الأقل"
    if p.lower() in ("12345678", "password", "123456789", "admin123", "كوبيجرين"):
        return False, "كلمة المرور ضعيفة جداً — اختر كلمة أقوى"
    return True, ""


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password, stored_hash):
    if not stored_hash:
        return False
    stored = str(stored_hash)
    if "$" not in stored:
        return password == stored
    try:
        salt, expected = stored.split("$", 1)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
        ).hex()
        return secrets.compare_digest(actual, expected)
    except Exception:
        return False


def password_strength_hint():
    return (
        f"🔒 كلمة المرور: {MIN_PASSWORD_LEN} أحرف على الأقل + حرف + رقم"
    )
