from aside_telegram.auth import (
    AUTH_MODE_LOCAL,
    AUTH_MODE_OAUTH,
    SCRUBBED_ENV_VARS,
    build_cli_env,
    scrub_process_env,
)

DIRTY = {
    "PATH": "/usr/bin",
    "HOME": "/home/x",
    "ANTHROPIC_API_KEY": "sk-ant-api-should-not-leak",
    "ANTHROPIC_AUTH_TOKEN": "tok",
    "CLAUDE_CODE_OAUTH_TOKEN": "stale-parent-token",
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "CLAUDE_CODE_USE_VERTEX": "1",
    "CLAUDE_CODE_USE_FOUNDRY": "1",
}


def test_oauth_token_is_only_credential():
    env, mode = build_cli_env("my-oauth-token", DIRTY)
    assert mode == AUTH_MODE_OAUTH
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "my-oauth-token"
    for key in SCRUBBED_ENV_VARS:
        if key != "CLAUDE_CODE_OAUTH_TOKEN":
            assert key not in env
    assert env["PATH"] == "/usr/bin" and env["HOME"] == "/home/x"


def test_no_token_falls_back_to_local_login_and_still_scrubs():
    for token in (None, "", "   "):
        env, mode = build_cli_env(token, DIRTY)
        assert mode == AUTH_MODE_LOCAL
        assert not any(k in env for k in SCRUBBED_ENV_VARS)


def test_never_injects_api_key():
    env, _ = build_cli_env("t", {"ANTHROPIC_API_KEY": "sk"})
    assert "ANTHROPIC_API_KEY" not in env


def test_input_env_not_mutated():
    src = dict(DIRTY)
    build_cli_env("t", src)
    assert src == DIRTY


def test_scrub_process_env():
    environ = dict(DIRTY)
    removed = scrub_process_env(environ)
    assert set(removed) == set(SCRUBBED_ENV_VARS)
    assert environ == {"PATH": "/usr/bin", "HOME": "/home/x"}
