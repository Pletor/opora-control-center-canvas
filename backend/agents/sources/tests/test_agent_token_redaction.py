"""Tokenové klíče se maskují bez ztráty číselné telemetrie."""

import pytest

from backend.agents.sources.agent_sources import redact


@pytest.mark.parametrize("key", [
    "authToken", "sessionToken", "idToken", "clientToken", "tokenValue",
    "AuthTOKEN", "TOKEN_VALUE", "refresh-token", "tokens", "authTokens",
    "access_token", "input_tokens", "inputTokens", "cache_read_input_tokens",
])
def test_opaque_token_value_is_redacted_recursively_without_mutating_source(key):
    # Záměrně nejde o rozpoznatelný textový formát klíče: rozhoduje strukturované pole.
    opaque = "opaque-credential-value"
    source = {"nested": [{key: opaque}], "status": "running"}
    result = redact(source)
    assert result == {"nested": [{key: "[REDACTED]"}], "status": "running"}
    assert source["nested"][0][key] == opaque


@pytest.mark.parametrize("key", [
    "input_tokens", "output_tokens", "cache_read_input_tokens",
    "cache_creation_input_tokens", "total_tokens", "inputTokens", "outputTokens",
])
def test_known_numeric_token_usage_is_not_a_credential(key):
    assert redact({key: 123}) == {key: 123}
