"""Versioned, explicitly supplied application configuration (not credentials).

Reads never create storage. Writes share runtime ownership and use a revision
check, an in-process mutex, and descriptor-relative atomic replacement.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
import re
import stat
import threading
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scanner.config.paths import ApplicationPaths

_mutex = threading.RLock()
_MAX_BYTES = 8192
_EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+")


class ConfigurationUnavailable(RuntimeError):
    pass


class ConfigurationConflict(RuntimeError):
    pass


def _printable(value: str) -> bool:
    return all(32 <= ord(character) <= 126 for character in value)


class SECIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    application_name: str = Field(min_length=1, max_length=120)
    contact_email: str = Field(min_length=3, max_length=254)

    @field_validator("application_name")
    @classmethod
    def application(cls, value: str) -> str:
        if not _printable(value) or not value.strip():
            raise ValueError("Use a nonempty application/organization name with printable ASCII characters")
        return value.strip()

    @field_validator("contact_email")
    @classmethod
    def email(cls, value: str) -> str:
        if not _printable(value) or not _EMAIL.fullmatch(value.strip()):
            raise ValueError("Enter a valid contact email address")
        return value.strip()

    @property
    def user_agent(self) -> str:
        return f"{self.application_name} {self.contact_email}"


class ApplicationConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1] = 1
    revision: int = Field(default=0, ge=0)
    sec_identity: SECIdentity | None = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Unsupported configuration version")
        return value


class EffectiveSECIdentity(BaseModel):
    source: Literal["explicit", "environment", "saved", "missing"]
    user_agent: str


def _declared_header(value: str) -> str:
    if not _printable(value):
        raise ConfigurationUnavailable("SEC_USER_AGENT must not contain control or non-ASCII characters")
    value = value.strip()
    parts = value.rsplit(None, 1)
    if (len(value) > 400 or len(parts) != 2
            or not _EMAIL.fullmatch(parts[-1].strip("()<>"))):
        raise ConfigurationUnavailable(
            "SEC_USER_AGENT must contain an application/organization name and contact email, without control characters"
        )
    return value


@contextmanager
def _directory(paths: ApplicationPaths, *, create: bool = False):
    root_fd = directory_fd = None
    try:
        if create:
            paths.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            root_fd = os.open(paths.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            if create:
                try:
                    os.mkdir("configuration", mode=0o700, dir_fd=root_fd)
                    os.fsync(root_fd)
                except FileExistsError:
                    pass
            directory_fd = os.open("configuration", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        except FileNotFoundError:
            if create:
                raise
        yield directory_fd
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
        if root_fd is not None:
            os.close(root_fd)


def _read(paths: ApplicationPaths) -> ApplicationConfiguration:
    with _directory(paths) as directory_fd:
        if directory_fd is None:
            return ApplicationConfiguration()
        try:
            fd = os.open(paths.application_settings.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        except FileNotFoundError:
            return ApplicationConfiguration()
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("Configuration must be a regular file")
            data = stream.read(_MAX_BYTES + 1)
        if len(data) > _MAX_BYTES:
            raise ValueError("Configuration too large")
        # Reject duplicate fields rather than silently accepting a different value.
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate configuration field")
                result[key] = value
            return result
        document = json.loads(data, object_pairs_hook=unique_pairs)
        if not isinstance(document, dict) or set(document) != {"schema_version", "revision", "sec_identity"}:
            raise ValueError("Unsupported configuration fields")
        configuration = ApplicationConfiguration.model_validate(document)
        if configuration.revision < 1:
            raise ValueError("Persisted configuration requires a positive revision")
        return configuration


def read_configuration(paths: ApplicationPaths | None = None) -> ApplicationConfiguration:
    try:
        return _read(paths or ApplicationPaths.resolve())
    except (OSError, ValueError, RecursionError) as error:
        raise ConfigurationUnavailable(
            "Application configuration is unreadable or unsupported. It was not replaced; preserve it and review recovery."
        ) from error


def effective_sec_identity(explicit: str | None = None, *, configuration: ApplicationConfiguration | None = None) -> EffectiveSECIdentity:
    if explicit:
        return EffectiveSECIdentity(source="explicit", user_agent=_declared_header(explicit))
    # Presence, even if blank/invalid, is deliberate: never silently use a saved
    # identity when the launcher intended an override.
    if "SEC_USER_AGENT" in os.environ:
        return EffectiveSECIdentity(source="environment", user_agent=_declared_header(os.environ["SEC_USER_AGENT"]))
    configuration = configuration if configuration is not None else read_configuration()
    if configuration.sec_identity is not None:
        return EffectiveSECIdentity(source="saved", user_agent=configuration.sec_identity.user_agent)
    return EffectiveSECIdentity(source="missing", user_agent="")


def save_sec_identity(identity: SECIdentity | None, expected_revision: int,
                      paths: ApplicationPaths | None = None) -> ApplicationConfiguration:
    from scanner.data.ownership import acquire_root

    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError("Expected revision must be a nonnegative integer")
    paths = paths or ApplicationPaths.resolve()
    ownership = acquire_root(paths.root)
    try:
        with _mutex:
            current = read_configuration(paths)
            if expected_revision != current.revision:
                raise ConfigurationConflict("Setup changed in another window. Reload saved setup before saving again.")
            configuration = ApplicationConfiguration(revision=current.revision + 1, sec_identity=identity)
            payload = configuration.model_dump_json(indent=2).encode("utf-8")
            with _directory(paths, create=True) as directory_fd:
                temporary = f"application-settings-{uuid4().hex}.tmp"
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(payload)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, paths.application_settings.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
                    os.fsync(directory_fd)
                finally:
                    try:
                        os.unlink(temporary, dir_fd=directory_fd)
                    except FileNotFoundError:
                        pass
            return configuration
    except OSError as error:
        raise ConfigurationUnavailable("Setup save could not be confirmed. Reload saved setup before trying again.") from error
    finally:
        del ownership
