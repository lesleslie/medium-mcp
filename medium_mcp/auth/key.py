from __future__ import annotations

from pydantic import SecretStr

from medium_mcp.utils.exceptions import ConfigurationError

# RapidAPI keys are >= 32 chars in practice; reject obviously-too-short values.
MIN_KEY_LENGTH = 32


def validate_rapidapi_key(key: SecretStr | None) -> str:
    """Return the unmasked RapidAPI key or raise ConfigurationError.

    Callers should invoke this at startup; the secret is only ever held in
    memory, never logged. ``mcp_common.security.APIKeyValidator.mask_key`` is
    used by logging paths that need a masked representation.
    """
    if key is None:
        raise ConfigurationError(
            "MEDIUM_MCP_RAPIDAPI_KEY is required",
            context={"env_var": "MEDIUM_MCP_RAPIDAPI_KEY"},
        )
    value = key.get_secret_value()
    if len(value) < MIN_KEY_LENGTH:
        raise ConfigurationError(
            "MEDIUM_MCP_RAPIDAPI_KEY is too short to be a valid RapidAPI key",
            context={"length": len(value), "min_required": MIN_KEY_LENGTH},
        )
    return value
