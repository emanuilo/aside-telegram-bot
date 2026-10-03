import pytest

from aside_telegram.config import ConfigError, load_settings, parse_allowed_user_ids


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, set()),
        ("", set()),
        ("  ", set()),
        ("123", {123}),
        ("123,456", {123, 456}),
        (" 123 , 456 ,, ", {123, 456}),
        ("123 456;789", {123, 456, 789}),
        ("-100123", {-100123}),
    ],
)
def test_parse_allowed_user_ids(raw, expected):
    assert parse_allowed_user_ids(raw) == frozenset(expected)


def test_parse_allowed_user_ids_rejects_garbage():
    with pytest.raises(ConfigError):
        parse_allowed_user_ids("123,@someone")


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for k in ("TELEGRAM_BOT_TOKEN", "ALLOWED_USER_IDS", "CLAUDE_CODE_OAUTH_TOKEN", "ASIDE_COMMAND"):
        monkeypatch.delenv(k, raising=False)
    empty = tmp_path / ".env"
    empty.write_text("")
    return empty


def test_load_settings_requires_allowlist(monkeypatch, clean_env):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    with pytest.raises(ConfigError, match="ALLOWED_USER_IDS"):
        load_settings(clean_env)


def test_load_settings_requires_token(monkeypatch, clean_env):
    monkeypatch.setenv("ALLOWED_USER_IDS", "1")
    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        load_settings(clean_env)


def test_load_settings_ok(monkeypatch, clean_env):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("ALLOWED_USER_IDS", "1,2")
    monkeypatch.setenv("ASIDE_COMMAND", "/opt/aside")
    s = load_settings(clean_env)
    assert s.allowed_user_ids == {1, 2}
    assert s.agent.aside_command == "/opt/aside"
    assert s.agent.model == "claude-sonnet-5-5"
    assert s.agent.effort == "medium"
    assert s.agent.oauth_token is None
