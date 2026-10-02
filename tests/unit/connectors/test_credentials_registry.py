from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from packages.connectors.base import BaseKnowledgeConnector, ConfigField, validate_against_schema
from packages.connectors.credentials import (
    CredentialCipher,
    CredentialConfigurationError,
    CredentialDecryptionError,
)
from packages.connectors.registry import ConnectorRegistry, default_registry


def key() -> str:
    return Fernet.generate_key().decode()


def test_credentials_round_trip_and_the_ciphertext_hides_the_secret():
    cipher = CredentialCipher(key())
    token = cipher.encrypt({"api_token": "TOP-SECRET", "email": "a@b.c"})
    assert "TOP-SECRET" not in token
    assert cipher.decrypt(token) == {"api_token": "TOP-SECRET", "email": "a@b.c"}


def test_without_a_key_nothing_can_be_stored():
    for missing in (None, "", "  , "):
        with pytest.raises(CredentialConfigurationError):
            CredentialCipher(missing)
    with pytest.raises(CredentialConfigurationError):
        CredentialCipher("not-a-fernet-key")


def test_key_rotation_reencrypts_under_the_new_primary_key():
    old, new = key(), key()
    token = CredentialCipher(old).encrypt({"s": 1})

    rotating = CredentialCipher(f"{new},{old}")  # new key first: encrypts; old key still decrypts
    assert rotating.decrypt(token) == {"s": 1}
    rotated = rotating.rotate(token)

    assert CredentialCipher(new).decrypt(rotated) == {"s": 1}  # the old key is no longer needed
    with pytest.raises(CredentialDecryptionError):
        CredentialCipher(old).decrypt(rotated)


def test_a_wrong_key_is_a_clear_error_not_garbage():
    token = CredentialCipher(key()).encrypt({"s": 1})
    with pytest.raises(CredentialDecryptionError):
        CredentialCipher(key()).decrypt(token)


def test_every_builtin_connector_is_registered_and_describes_its_settings_for_the_ui():
    registry = default_registry()
    infos = {i.type: i for i in registry.infos()}
    for available in ("web", "wikipedia", "confluence", "microsoft_teams", "sharepoint", "onedrive"):
        assert infos[available].available and infos[available].config_schema
    for planned in ("google_drive", "notion", "github", "slack", "s3"):
        assert not infos[planned].available  # named, extensible, not built
    assert "upload" not in infos  # uploads are not a connector


def test_a_new_connector_needs_no_change_outside_its_own_class():
    class DemoConnector(BaseKnowledgeConnector):
        type = "s3"
        display_name = "Demo bucket"
        config_schema = (ConfigField("bucket", "Bucket", required=True),)

        async def test_connection(self):
            raise NotImplementedError

        def discover(self, context):
            raise NotImplementedError

        async def fetch(self, document):
            raise NotImplementedError

    registry = ConnectorRegistry()
    registry.register(DemoConnector)
    assert registry.is_available("s3")
    assert registry.create("s3", {"bucket": "b"}).configuration["bucket"] == "b"
    with pytest.raises(KeyError):
        registry.get("box")


def test_unknown_source_types_cannot_be_registered():
    class Bad(BaseKnowledgeConnector):
        type = "myspace"
        display_name = "x"

        async def test_connection(self): ...
        def discover(self, context): ...
        async def fetch(self, document): ...

    with pytest.raises(ValueError):
        ConnectorRegistry().register(Bad)


def test_schema_validation_covers_types_ranges_options_and_unknown_keys():
    fields = (
        ConfigField("url", "URL", "url", required=True),
        ConfigField("n", "Count", "number", minimum=1, maximum=5),
        ConfigField("mode", "Mode", "select", options=("a", "b")),
        ConfigField("flag", "Flag", "boolean"),
        ConfigField("items", "Items", "string_list"),
    )
    assert validate_against_schema(fields, {"url": "https://x.test", "n": 3, "mode": "a", "flag": True, "items": ["x"]}).ok
    result = validate_against_schema(fields, {"url": "ftp://x", "n": 9, "mode": "z", "flag": "yes", "items": [""], "extra": 1})
    assert len(result.errors) == 6
    assert not validate_against_schema(fields, {}).ok  # required
