import pytest
from loguru import logger

from hometabs.auth import (
    AUTH_MODE_API_KEY,
    AUTH_MODE_LOCAL,
    AUTH_MODE_OAUTH,
    SCRUBBED_ENV_VARS,
    build_cli_env,
    log_auth_choice,
    scrub_process_env,
    select_credential,
)

API_KEY = "sk-ant-api03-test-key-should-not-leak"
OAUTH = "sk-ant-oat01-test-token-should-not-leak"

DIRTY = {
    "PATH": "/usr/bin",
    "HOME": "/home/x",
    "ANTHROPIC_API_KEY": "stale-parent-api-key",
    "ANTHROPIC_AUTH_TOKEN": "tok",
    "CLAUDE_CODE_OAUTH_TOKEN": "stale-parent-token",
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "CLAUDE_CODE_USE_VERTEX": "1",
    "CLAUDE_CODE_USE_FOUNDRY": "1",
}


def _only_credential(env, name, value):
    assert env[name] == value
    for key in SCRUBBED_ENV_VARS:
        if key != name:
            assert key not in env, key
    assert env["PATH"] == "/usr/bin" and env["HOME"] == "/home/x"


@pytest.mark.parametrize(
    "api_key, oauth, mode, secret",
    [
        (API_KEY, OAUTH, AUTH_MODE_API_KEY, API_KEY),  # API key wins
        (API_KEY, None, AUTH_MODE_API_KEY, API_KEY),
        (f"  {API_KEY}\n", "", AUTH_MODE_API_KEY, API_KEY),  # stripped
        (None, OAUTH, AUTH_MODE_OAUTH, OAUTH),
        ("   ", OAUTH, AUTH_MODE_OAUTH, OAUTH),  # blank key is ignored
        (None, None, AUTH_MODE_LOCAL, None),
        ("", "  ", AUTH_MODE_LOCAL, None),
    ],
)
def test_select_credential_precedence(api_key, oauth, mode, secret):
    cred = select_credential(api_key, oauth)
    assert (cred.mode, cred.secret) == (mode, secret)


def test_credential_repr_hides_secret():
    cred = select_credential(API_KEY, None)
    assert API_KEY not in repr(cred) and API_KEY not in str(cred)
    assert "api_key" in repr(cred)


def test_api_key_is_only_credential():
    env, mode = build_cli_env(API_KEY, None, DIRTY)
    assert mode == AUTH_MODE_API_KEY
    _only_credential(env, "ANTHROPIC_API_KEY", API_KEY)


def test_api_key_wins_over_oauth_token():
    env, mode = build_cli_env(API_KEY, OAUTH, DIRTY)
    assert mode == AUTH_MODE_API_KEY
    _only_credential(env, "ANTHROPIC_API_KEY", API_KEY)


def test_oauth_token_is_only_credential():
    env, mode = build_cli_env(None, OAUTH, DIRTY)
    assert mode == AUTH_MODE_OAUTH
    _only_credential(env, "CLAUDE_CODE_OAUTH_TOKEN", OAUTH)


def test_nothing_set_falls_back_to_local_login_and_still_scrubs():
    for api_key, token in ((None, None), ("", ""), ("   ", "   ")):
        env, mode = build_cli_env(api_key, token, DIRTY)
        assert mode == AUTH_MODE_LOCAL
        assert not any(k in env for k in SCRUBBED_ENV_VARS)


def test_parent_env_credentials_are_never_reused():
    # Only the explicitly configured values count, never stale parent vars.
    env, mode = build_cli_env(None, None, DIRTY)
    assert mode == AUTH_MODE_LOCAL
    assert "stale-parent-api-key" not in env.values()
    assert "stale-parent-token" not in env.values()


def test_input_env_not_mutated():
    src = dict(DIRTY)
    build_cli_env(API_KEY, OAUTH, src)
    assert src == DIRTY


def test_scrub_process_env():
    environ = dict(DIRTY)
    removed = scrub_process_env(environ)
    assert set(removed) == set(SCRUBBED_ENV_VARS)
    assert environ == {"PATH": "/usr/bin", "HOME": "/home/x"}


@pytest.fixture
def log_lines():
    lines: list[str] = []
    handler = logger.add(lambda m: lines.append(str(m)), level="DEBUG")
    yield lines
    logger.remove(handler)


@pytest.mark.parametrize(
    "api_key, oauth, mode, expect",
    [
        (API_KEY, OAUTH, AUTH_MODE_API_KEY, "using the API key"),
        (API_KEY, None, AUTH_MODE_API_KEY, "ANTHROPIC_API_KEY"),
        (None, OAUTH, AUTH_MODE_OAUTH, "CLAUDE_CODE_OAUTH_TOKEN"),
        (None, None, AUTH_MODE_LOCAL, "local Claude Code login"),
    ],
)
def test_log_auth_choice_logs_mode_never_values(log_lines, api_key, oauth, mode, expect):
    assert log_auth_choice(api_key, oauth) == mode
    text = "\n".join(log_lines)
    assert mode in text and expect in text
    assert API_KEY not in text and OAUTH not in text
    if not (api_key and oauth):
        assert "Both" not in text
