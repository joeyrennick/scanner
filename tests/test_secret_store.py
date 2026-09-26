import sqlite3
import base64
import os

import pytest

from scanner.security.secret_store import SQLiteSecretStore


def test_secret_store_round_trips_encrypted_secret(tmp_path):
    db_path = tmp_path / "market_data.sqlite"
    store = SQLiteSecretStore(db_path)

    store.set_secret("massive_api_key", "secret-value")

    assert store.get_secret("massive_api_key") == "secret-value"
    assert store.metadata("massive_api_key").configured is True

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT encrypted_value FROM secrets WHERE name = ?",
            ("massive_api_key",),
        ).fetchone()

    assert row is not None
    assert "secret-value" not in row[0]


def test_secret_store_persists_across_instances(tmp_path):
    db_path = tmp_path / "market_data.sqlite"

    SQLiteSecretStore(db_path).set_secret("massive_api_key", "secret-value")

    assert SQLiteSecretStore(db_path).get_secret("massive_api_key") == "secret-value"


def test_secret_store_delete_secret(tmp_path):
    store = SQLiteSecretStore(tmp_path / "market_data.sqlite")
    store.set_secret("massive_api_key", "secret-value")

    assert store.delete_secret("massive_api_key") is True
    assert store.get_secret("massive_api_key") is None
    assert store.metadata("massive_api_key").configured is False


def test_secret_store_rejects_wrong_local_key(tmp_path):
    db_path = tmp_path / "market_data.sqlite"
    first_key = tmp_path / "first.key"
    second_key = tmp_path / "second.key"

    SQLiteSecretStore(db_path, key_path=first_key).set_secret(
        "massive_api_key",
        "secret-value",
    )
    second_key.write_bytes(base64.urlsafe_b64encode(os.urandom(32)))

    with pytest.raises(ValueError, match="authentication failed"):
        SQLiteSecretStore(db_path, key_path=second_key).get_secret("massive_api_key")


def test_missing_key_is_never_replaced_for_existing_credentials(tmp_path):
    store = SQLiteSecretStore(tmp_path / "credentials.sqlite")
    store.set_secret("massive_api_key", "test-secret")
    original_key = store.key_path.read_bytes()
    store.key_path.unlink()
    with pytest.raises(ValueError, match="Missing credential key"):
        store.get_secret("massive_api_key")
    with pytest.raises(ValueError, match="Missing credential key"):
        store.set_secret("another_key", "another-test-secret")
    assert not store.key_path.exists()
    store.key_path.write_bytes(original_key)
    assert store.get_secret("massive_api_key") == "test-secret"


def test_empty_store_read_does_not_create_a_key(tmp_path):
    store = SQLiteSecretStore(tmp_path / "credentials.sqlite")
    assert store.get_secret("missing") is None
    assert not store.key_path.exists()
