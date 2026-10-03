"""Telegram bot wrapping a Claude Agent SDK browsing agent (Aside MCP)."""

from __future__ import annotations

import os
import sys

from loguru import logger

__all__ = ["main"]


def main() -> None:
    """Console entry point: ``uv run aside-telegram``."""
    from .auth import AUTH_MODE_OAUTH, scrub_process_env
    from .config import ConfigError, load_settings

    logger.remove()
    logger.add(sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO"))

    try:
        settings = load_settings()
    except ConfigError as exc:
        logger.error("Configuration error: {}", exc)
        raise SystemExit(2) from exc

    # The SDK merges options.env over os.environ, so credentials must be
    # removed from this process too (the OAuth token was already captured
    # into settings and is re-injected explicitly for the CLI subprocess).
    removed = scrub_process_env()
    if "ANTHROPIC_API_KEY" in removed:
        logger.warning("Ignoring ANTHROPIC_API_KEY from the environment: billing must use the subscription")
    if settings.agent.oauth_token:
        logger.info("Claude auth: subscription via CLAUDE_CODE_OAUTH_TOKEN ({})", AUTH_MODE_OAUTH)
    else:
        logger.warning(
            "Claude auth: CLAUDE_CODE_OAUTH_TOKEN not set; falling back to the local "
            "Claude Code login (still subscription). Run `claude setup-token` for a long-lived token."
        )
    if os.environ.get("ANTHROPIC_BASE_URL"):
        logger.warning("ANTHROPIC_BASE_URL is set; the Claude CLI will use it")
    logger.info(
        "Starting aside-telegram (model={}, effort={}, aside={}, allowed users={})",
        settings.agent.model, settings.agent.effort, settings.agent.aside_command,
        sorted(settings.allowed_user_ids),
    )

    from telegram.error import InvalidToken

    from .bot import AsideBot

    app = AsideBot(settings).build_application()
    try:
        app.run_polling(allowed_updates=["message"], drop_pending_updates=True)
    except InvalidToken:
        logger.error("Telegram rejected TELEGRAM_BOT_TOKEN; check the token from @BotFather.")
        raise SystemExit(2) from None
