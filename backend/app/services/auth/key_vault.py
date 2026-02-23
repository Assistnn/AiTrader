"""
KeyVault: API key encryption/decryption with AES-256-GCM.

Reference: 11_セキュリティ Section 4【監査3】

Master key MUST NOT be stored in database.
Management priority:
  1. Environment variable: MASTER_ENCRYPTION_KEY
  2. File reference: /etc/secrets/master_key (perm 600)
  3. External: AWS Secrets Manager / GCP Secret Manager

Encryption:
  - Algorithm: AES-256-GCM (authenticated encryption)
  - Key derivation: HKDF from master key
  - IV: random 12 bytes per encryption
  - Stored format: IV (12) + tag (16) + ciphertext (N) bytes
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


class KeyVault:
    """API key encryption/decryption. Reference: Section 4-2"""

    IV_LENGTH = 12
    TAG_LENGTH = 16  # GCM tag is appended to ciphertext by cryptography lib

    def __init__(self, master_key: str | bytes):
        if isinstance(master_key, str):
            master_key = master_key.encode("utf-8")
        self._derived_key = self._derive_key(master_key)

    def _derive_key(self, master_key: bytes) -> bytes:
        """Derive a 256-bit key from master key using HKDF."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"ai-trading-key-vault",
        )
        return hkdf.derive(master_key)

    def encrypt(self, plaintext: str) -> bytes:
        """
        Encrypt an API key.

        Returns:
            IV (12 bytes) + ciphertext+tag (N+16 bytes)
        """
        iv = os.urandom(self.IV_LENGTH)
        aesgcm = AESGCM(self._derived_key)
        # AESGCM.encrypt returns ciphertext + 16-byte tag
        ct_with_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
        return iv + ct_with_tag

    def decrypt(self, encrypted: bytes) -> str:
        """
        Decrypt an encrypted API key.

        Args:
            encrypted: IV (12) + ciphertext+tag bytes
        """
        iv = encrypted[: self.IV_LENGTH]
        ct_with_tag = encrypted[self.IV_LENGTH :]
        aesgcm = AESGCM(self._derived_key)
        plaintext = aesgcm.decrypt(iv, ct_with_tag, None)
        return plaintext.decode("utf-8")
