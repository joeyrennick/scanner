import sqlite3

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

    with pytest.raises(ValueError, match="authentication failed"):
        SQLiteSecretStore(db_path, key_path=second_key).get_secret("massive_api_key")
