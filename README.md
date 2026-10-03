# aside-telegram

A Telegram bot that gives you a browsing agent in your pocket. Each chat is a
persistent [Claude Agent SDK](https://pypi.org/project/claude-agent-sdk/)
conversation (Sonnet 5.5, medium effort) whose only tool is the
Aside MCP `repl`, which drives your real Aside Browser.

- Billing goes through your **Claude subscription** (`CLAUDE_CODE_OAUTH_TOKEN`
  or your local Claude Code login). `ANTHROPIC_API_KEY` is always scrubbed.
- Only allowlisted Telegram user IDs can talk to it; it refuses to start
  without an allowlist.
- The agent has no shell or file tools, just `mcp__aside__repl`. It's told to
  ask you before anything irreversible (purchases, sending messages, submitting
  forms, deleting).

## Setup

Requires Python 3.10+, [uv](https://docs.astral.sh/uv/), Claude Code and Aside
(`aside mcp` must work).

1. **Claude subscription token**

   ```sh
   claude setup-token
   ```

   Copy the printed token into `CLAUDE_CODE_OAUTH_TOKEN`. If you leave it
   empty, the bot falls back to your local Claude Code login (`claude` then
   `/login`), which also bills the subscription.

2. **Telegram bot**: message [@BotFather](https://t.me/BotFather), `/newbot`,
   and copy the token into `TELEGRAM_BOT_TOKEN`.

3. **Your Telegram user ID**: ask [@userinfobot](https://t.me/userinfobot), or
   start the bot and message it. Rejected users are logged with their ID and
   told their ID in a private chat. Put it in `ALLOWED_USER_IDS` (comma-separated).

4. **Configure and install**

   ```sh
   cp .env.example .env   # then fill it in
   uv sync
   ```

5. **Run**

   ```sh
   uv run aside-telegram
   # or: uv run python -m aside_telegram
   ```

## Usage

Send any text, e.g. *"Open example.com and tell me the heading"*. While the
agent works you'll see "typing…" and a status line showing the current browser
step. Screenshots the agent `display()`s are forwarded as photos.

| Command  | Effect |
|----------|--------|
| `/start` | Help |
| `/new`   | Forget the conversation and start fresh |
| `/stop`  | Interrupt the running task and drop any queued messages |

Messages sent while a task runs are queued and handled in order (one agent
turn per chat at a time). Conversations survive restarts: chat → session IDs
are stored in `.state/sessions.json` and resumed. Messages sent while the bot
was offline are dropped on startup, so stale commands don't run in your browser.

## Layout

```
src/aside_telegram/
  agent.py       # Agent core (no Telegram): ClaudeSDKClient + aside MCP
  auth.py        # Subscription-only env for the Claude CLI subprocess
  config.py      # .env loading and validation
  formatting.py  # 4096-char splitting, Markdown -> Telegram HTML
  bot.py         # Telegram handlers, per-chat locks, progress, photos
tests/           # pytest suite for the pure helpers
```

## Development

```sh
uv run pytest
```
