"""Hometabs: a personal agent in Telegram that uses your real browser (via the Aside MCP)."""

from __future__ import annotations

import os
import sys

from loguru import logger

__all__ = ["main"]


def main() -> None:
    """Console entry point: ``uv run hometabs``."""
    from .auth import log_auth_choice, scrub_process_env
    from .config import ConfigError, load_settings

    logger.remove()
    # diagnose=False: loguru would otherwise print local variable values in
    # tracebacks, and python-telegram-bot's Bot repr contains the bot token.
    logger.add(sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO"), diagnose=False)

    try:
        settings = load_settings()
    except ConfigError as exc:
        logger.error("Configuration error: {}", exc)
        raise SystemExit(2) from exc

    # The SDK merges options.env over os.environ, so credentials must be
    # removed from this process too (the chosen credential was already
    # captured into settings and is re-injected explicitly for the CLI).
    scrub_process_env()
    log_auth_choice(settings.agent.api_key, settings.agent.oauth_token)
    if os.environ.get("ANTHROPIC_BASE_URL"):
        logger.warning("ANTHROPIC_BASE_URL is set; the Claude CLI will use it")
    logger.info(
        "Starting Hometabs (default model={}, default effort={}, aside={}, allowed users={})",
        settings.agent.model,
        settings.agent.effort,
        settings.agent.aside_command,
        sorted(settings.allowed_user_ids),
    )

    from telegram.error import InvalidToken

    from .bot import HometabsBot

    app = HometabsBot(settings).build_application()
    try:
        app.run_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=True)
    except InvalidToken:
        logger.error("Telegram rejected TELEGRAM_BOT_TOKEN; check the token from @BotFather.")
        raise SystemExit(2) from None
