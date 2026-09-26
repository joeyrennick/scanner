from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from scanner.data.ownership import acquire_database, connect
import base64
import hmac
import hashlib
import os
import sqlite3
import threading


PAYLOAD_PREFIX = b"SS1"
NONCE_BYTES = 16
TAG_BYTES = 32
MASTER_KEY_BYTES = 32
_KEY_LOCK = threading.RLock()


@dataclass(frozen=True)
class SecretMetadata:
    name: str
    configured: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SQLiteSecretStore:
    def __init__(self, db_path: str | Path, key_path: str | Path | None = None):
        self.db_path = Path(db_path)
        self._ownership = acquire_database(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_path = Path(key_path) if key_path else self.db_path.with_suffix(".key")
        self._ensure_schema()

    def get_secret(self, name: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT encrypted_value
                FROM secrets
                WHERE name = ?
                """,
                (name,),
            ).fetchone()

        if row is None:
            return None

        return _decrypt(row[0], self._master_key())

    def set_secret(self, name: str, value: str) -> None:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        encrypted_value = _encrypt(value, self._master_key(allow_create=True))

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO secrets (name, encrypted_value, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name)
                DO UPDATE SET
                    encrypted_value = excluded.encrypted_value,
                    updated_at = excluded.updated_at
                """,
                (name, encrypted_value, now, now),
            )

    def delete_secret(self, name: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM secrets
                WHERE name = ?
                """,
                (name,),
            )

        return bool(cursor.rowcount)

    def metadata(self, name: str) -> SecretMetadata:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT created_at, updated_at
                FROM secrets
                WHERE name = ?
                """,
                (name,),
            ).fetchone()

        if row is None:
            return SecretMetadata(name=name, configured=False)

        return SecretMetadata(
            name=name,
            configured=True,
            created_at=datetime.fromisoformat(row[0]) if row[0] else None,
            updated_at=datetime.fromisoformat(row[1]) if row[1] else None,
        )

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS secrets (
                    name TEXT PRIMARY KEY,
                    encrypted_value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _master_key(self, *, allow_create: bool = False) -> bytes:
        with _KEY_LOCK:
            if self.key_path.is_symlink():
                raise ValueError("Credential key must not be a symlink")
            if self.key_path.exists():
                key = base64.b64decode(self.key_path.read_bytes(), altchars=b"-_", validate=True)
                if len(key) != MASTER_KEY_BYTES:
                    raise ValueError("Invalid credential key; restore the matching original key")
                return key

            with self._connect() as connection:
                has_secrets = connection.execute("SELECT 1 FROM secrets LIMIT 1").fetchone() is not None
            if not allow_create or has_secrets:
                raise ValueError("Missing credential key; restore the matching original key before continuing")

            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            key = os.urandom(MASTER_KEY_BYTES)
            fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(base64.urlsafe_b64encode(key))
                stream.flush()
                os.fsync(stream.fileno())
            return key

    def _connect(self) -> sqlite3.Connection:
        return connect(self.db_path, timeout=30, kind="credential")


def _encrypt(value: str, key: bytes) -> str:
    nonce = os.urandom(NONCE_BYTES)
    plaintext = value.encode("utf-8")
    ciphertext = _xor_bytes(plaintext, _keystream(key=key, nonce=nonce, length=len(plaintext)))
    tag = hmac.new(key, PAYLOAD_PREFIX + nonce + ciphertext, hashlib.sha256).digest()
    payload = PAYLOAD_PREFIX + nonce + tag + ciphertext
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decrypt(encrypted_value: str, key: bytes) -> str:
    payload = base64.urlsafe_b64decode(encrypted_value.encode("ascii"))

    if not payload.startswith(PAYLOAD_PREFIX):
        raise ValueError("Unsupported encrypted secret payload")

    offset = len(PAYLOAD_PREFIX)
    nonce = payload[offset : offset + NONCE_BYTES]
    offset += NONCE_BYTES
    tag = payload[offset : offset + TAG_BYTES]
    offset += TAG_BYTES
    ciphertext = payload[offset:]
    expected_tag = hmac.new(
        key,
        PAYLOAD_PREFIX + nonce + ciphertext,
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Encrypted secret authentication failed")

    plaintext = _xor_bytes(ciphertext, _keystream(key=key, nonce=nonce, length=len(ciphertext)))
    return plaintext.decode("utf-8")


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    blocks = []
    counter = 0

    while sum(len(block) for block in blocks) < length:
        counter_bytes = counter.to_bytes(8, "big")
        blocks.append(hmac.new(key, nonce + counter_bytes, hashlib.sha256).digest())
        counter += 1

    return b"".join(blocks)[:length]


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(left_byte ^ right_byte for left_byte, right_byte in zip(left, right))
