"""
Authentication & security layer tests.
Reference: 11_セキュリティ, 08_API仕様
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.services.auth.password import (
    hash_password,
    verify_password,
    validate_password_strength,
)
from app.services.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.services.auth.key_vault import KeyVault
from app.services.auth.log_masking import mask_secrets, mask_api_key, SecretMaskingFilter
from app.api.middleware.tenant_aware import TenantAwareSession


# ===========================================================================
# Password hashing (bcrypt)
# ===========================================================================


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "TestPass123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("CorrectPass1")
        assert verify_password("WrongPass1", hashed) is False

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("SamePass1")
        h2 = hash_password("SamePass1")
        assert h1 != h2  # bcrypt uses random salt

    def test_validate_strength_too_short(self):
        ok, msg = validate_password_strength("short1")
        assert ok is False
        assert "8 characters" in msg

    def test_validate_strength_no_digits(self):
        ok, msg = validate_password_strength("NoDigitsHere")
        assert ok is False
        assert "letters and numbers" in msg

    def test_validate_strength_no_letters(self):
        ok, msg = validate_password_strength("12345678")
        assert ok is False
        assert "letters and numbers" in msg

    def test_validate_strength_valid(self):
        ok, msg = validate_password_strength("ValidPass1")
        assert ok is True
        assert msg == ""


# ===========================================================================
# JWT tokens
# ===========================================================================


class TestJWT:
    def test_create_and_decode_access_token(self):
        token = create_access_token(user_id=42)
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        token = create_refresh_token(user_id=42)
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["type"] == "refresh"

    def test_invalid_token_returns_none(self):
        payload = decode_token("invalid.token.here")
        assert payload is None

    def test_tampered_token_returns_none(self):
        token = create_access_token(user_id=1)
        # Tamper with the payload
        parts = token.split(".")
        parts[1] = parts[1][:-2] + "XX"
        tampered = ".".join(parts)
        assert decode_token(tampered) is None

    def test_access_and_refresh_have_different_types(self):
        access = decode_token(create_access_token(1))
        refresh = decode_token(create_refresh_token(1))
        assert access["type"] == "access"
        assert refresh["type"] == "refresh"


# ===========================================================================
# KeyVault (AES-256-GCM)【監査3】
# ===========================================================================


class TestKeyVault:
    def test_encrypt_decrypt_roundtrip(self):
        vault = KeyVault("test-master-key-for-unit-tests-1234")
        plaintext = "my-secret-api-key-123"
        encrypted = vault.encrypt(plaintext)
        decrypted = vault.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypted_is_different_from_plaintext(self):
        vault = KeyVault("test-master-key-for-unit-tests-1234")
        plaintext = "my-secret-api-key-123"
        encrypted = vault.encrypt(plaintext)
        assert encrypted != plaintext.encode()

    def test_different_encryptions_produce_different_ciphertext(self):
        vault = KeyVault("test-master-key-for-unit-tests-1234")
        plaintext = "same-key-encrypted-twice"
        e1 = vault.encrypt(plaintext)
        e2 = vault.encrypt(plaintext)
        assert e1 != e2  # different IVs

    def test_wrong_key_fails_to_decrypt(self):
        vault1 = KeyVault("correct-master-key-1234567890123")
        vault2 = KeyVault("wrong-master-key-9876543210123456")
        encrypted = vault1.encrypt("secret")
        with pytest.raises(Exception):
            vault2.decrypt(encrypted)

    def test_tampered_ciphertext_fails(self):
        vault = KeyVault("test-master-key-for-unit-tests-1234")
        encrypted = vault.encrypt("my-api-key")
        tampered = bytearray(encrypted)
        tampered[-1] ^= 0xFF  # flip last byte
        with pytest.raises(Exception):
            vault.decrypt(bytes(tampered))

    def test_bytes_master_key(self):
        vault = KeyVault(b"bytes-master-key-for-testing-1234")
        assert vault.decrypt(vault.encrypt("test")) == "test"

    def test_encrypted_format_has_iv_prefix(self):
        vault = KeyVault("test-master-key-for-unit-tests-1234")
        encrypted = vault.encrypt("key")
        # IV is 12 bytes, then ciphertext + 16-byte tag
        assert len(encrypted) > 12 + 16


# ===========================================================================
# Log masking
# ===========================================================================


class TestLogMasking:
    def test_mask_api_key_in_json(self):
        text = '{"api_key": "abcdef12345678"}'
        masked = mask_secrets(text)
        assert "abcdef12345678" not in masked
        assert "****" in masked

    def test_mask_password_in_json(self):
        text = '{"password": "mysecretpass"}'
        masked = mask_secrets(text)
        assert "mysecretpass" not in masked
        assert "********" in masked

    def test_mask_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.xxx"
        masked = mask_secrets(text)
        assert "eyJhbGciOiJIUzI1NiJ9" not in masked
        assert "****..." in masked

    def test_mask_api_key_helper(self):
        assert mask_api_key("abcdefghijklmnop") == "****mnop"
        assert mask_api_key("ab") == "****"


# ===========================================================================
# TenantAwareSession【監査1】
# ===========================================================================


class TestTenantAwareSession:
    def test_permission_error_on_delete_other_user(self):
        """TenantAwareSession prevents deleting resources of other users."""

        class FakeModel:
            user_id = 999  # belongs to user 999

        class FakeSession:
            async def delete(self, instance):
                pass

        session = TenantAwareSession(FakeSession(), user_id=1)
        with pytest.raises(PermissionError):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                session.delete(FakeModel())
            )

    def test_add_sets_user_id(self):
        """TenantAwareSession auto-sets user_id on add."""

        class FakeModel:
            user_id = None

        class FakeSession:
            added = []
            def add(self, instance):
                self.added.append(instance)

        session = TenantAwareSession(FakeSession(), user_id=42)
        model = FakeModel()
        session.add(model)
        assert model.user_id == 42


# ===========================================================================
# verify_ownership
# ===========================================================================


class TestVerifyOwnership:
    def test_module_importable(self):
        """verify_trader_ownership function is importable."""
        from app.api.middleware.verify_ownership import verify_trader_ownership
        assert callable(verify_trader_ownership)
