# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-03

### Added

- Telegram bot (python-telegram-bot, long polling) in front of a Claude Agent
  SDK agent whose only browser tool is the aside MCP `repl`, driving your Aside
  Browser.
- Mandatory allowlist of Telegram user IDs (`ALLOWED_USER_IDS`); the bot won't
  start without one.
- Subscription-only billing: `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`
  or the local Claude Code login. `ANTHROPIC_API_KEY` and other provider
  credentials are scrubbed.
- Locked-down agent: no shell or file tools, no user settings, CLAUDE.md,
  plugins or other MCP servers; non-approved tools are denied.
- One persistent conversation per chat, resumed after restarts
  (`.state/sessions.json`); sessions started under different instructions are
  not resumed.
- `/start`, `/new`, `/stop`, `/model` and `/effort` commands. The model list and
  supported effort levels come from Anthropic's `/v1/models` (cached for 24h);
  the choice is saved in `.state/settings.json` and applied without losing the
  conversation.
- Progress messages for each browser step, a typing indicator, a queue for
  messages sent while a task runs, Markdown to Telegram HTML conversion,
  splitting of long replies, and screenshots forwarded as photos.
- Skills: a `sign-in` skill shipped with the bot, plus Aside's builtin
  `1password` skill copied from the local Aside install at startup
  (`ASIDE_SKILLS_DIR`).
- Agent instructions ask for confirmation in chat before irreversible actions.

[Unreleased]: https://github.com/emanuilo/aside-telegram-bot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/emanuilo/aside-telegram-bot/releases/tag/v0.1.0
