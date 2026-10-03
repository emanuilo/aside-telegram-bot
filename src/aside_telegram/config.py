"""Configuration loaded from environment / .env."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_ASIDE_COMMAND = shutil.which("aside") or str(Path.home() / ".local/bin/aside")
# Where Aside keeps its builtin skills (profile 0); see skills.py.
DEFAULT_ASIDE_SKILLS_DIR = Path.home() / ".aside" / "u" / "0" / "skills" / "builtin"
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_EFFORT = "medium"


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


def parse_allowed_user_ids(raw: str | None) -> frozenset[int]:
    """Parse a comma/whitespace separated list of Telegram user IDs.

    Raises ConfigError on any non-integer entry so a typo can't silently
    lock out (or worse, mis-configure) the allowlist.
    """
    if not raw:
        return frozenset()
    ids: set[int] = set()
    for part in raw.replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError as exc:
            raise ConfigError(f"ALLOWED_USER_IDS contains a non-integer entry: {part!r}") from exc
    return frozenset(ids)


@dataclass(frozen=True)
class AgentConfig:
    """Everything the agent core needs (no Telegram)."""

    aside_command: str = DEFAULT_ASIDE_COMMAND
    aside_args: tuple[str, ...] = ("mcp",)
    model: str = DEFAULT_MODEL
    effort: str | None = DEFAULT_EFFORT  # None: let the CLI/model default apply
    oauth_token: str | None = None
    max_turns: int | None = 60
    cwd: Path | None = None
    # Source of Aside's builtin skills, copied into the plugin at startup.
    aside_skills_dir: Path | None = DEFAULT_ASIDE_SKILLS_DIR
    # The built plugin (see skills.build_plugin) and its allowlisted skills.
    plugin_dir: Path | None = None
    skills: tuple[str, ...] = ()


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    allowed_user_ids: frozenset[int]
    agent: AgentConfig = field(default_factory=AgentConfig)
    state_file: Path = Path(".state/sessions.json")


def _path_env(name: str, default: Path) -> Path:
    value = (os.environ.get(name) or "").strip()
    return Path(value).expanduser() if value else default


def load_agent_config(env_file: str | os.PathLike | None = None) -> AgentConfig:
    load_dotenv(env_file, override=False)
    return AgentConfig(
        aside_command=os.environ.get("ASIDE_COMMAND") or DEFAULT_ASIDE_COMMAND,
        model=os.environ.get("ASIDE_BOT_MODEL") or DEFAULT_MODEL,
        effort=os.environ.get("ASIDE_BOT_EFFORT") or DEFAULT_EFFORT,
        oauth_token=(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or "").strip() or None,
        aside_skills_dir=_path_env("ASIDE_SKILLS_DIR", DEFAULT_ASIDE_SKILLS_DIR),
    )


def load_settings(env_file: str | os.PathLike | None = None) -> Settings:
    """Load and validate bot settings. Raises ConfigError if unusable."""
    agent = load_agent_config(env_file)
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise ConfigError("TELEGRAM_BOT_TOKEN is not set (see .env.example).")
    allowed = parse_allowed_user_ids(os.environ.get("ALLOWED_USER_IDS"))
    if not allowed:
        raise ConfigError(
            "ALLOWED_USER_IDS is empty. This bot controls a real browser, so an "
            "allowlist of Telegram user IDs is mandatory."
        )
    state_file = Path(os.environ.get("STATE_FILE") or ".state/sessions.json")
    return Settings(
        telegram_bot_token=token,
        allowed_user_ids=allowed,
        agent=agent,
        state_file=state_file,
    )
