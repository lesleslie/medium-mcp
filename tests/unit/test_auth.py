from __future__ import annotations

import pytest
from pydantic import SecretStr

from medium_mcp.auth.key import validate_rapidapi_key
from medium_mcp.utils.exceptions import ConfigurationError


def test_missing_key_raises_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        validate_rapidapi_key(None)


def test_short_key_raises_configuration_error() -> None:
    """RapidAPI keys are typically 50+ chars; reject obviously-too-short values."""
    with pytest.raises(ConfigurationError):
        validate_rapidapi_key(SecretStr("short"))


def test_valid_key_returned_unmasked() -> None:
    fake = "a" * 50
    assert validate_rapidapi_key(SecretStr(fake)) == fake


def test_masked_in_logs() -> None:
    from mcp_common.security import APIKeyValidator

    fake = "abcdef123456" + "x" * 40
    masked = APIKeyValidator.mask_key(fake, visible_chars=4)
    # mask_key keeps the LAST ``visible_chars`` and elides the rest.
    assert masked.endswith("xxxx")
    assert "abcdef123456" not in masked
