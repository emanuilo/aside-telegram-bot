# aside-telegram

A Telegram bot that gives you a browsing agent in your pocket. Each chat is a
persistent [Claude Agent SDK](https://pypi.org/project/claude-agent-sdk/)
conversation (Sonnet 5.5, medium effort by default; switchable with `/model`
and `/effort`) whose only tool is the
Aside MCP `repl`, which drives your real Aside Browser.

- Billing goes through your **Claude subscription** (`CLAUDE_CODE_OAUTH_TOKEN`
  or your local Claude Code login). `ANTHROPIC_API_KEY` is always scrubbed.
- Only allowlisted Telegram user IDs can talk to it; it refuses to start
  without an allowlist.
- The agent has no shell or file tools, just `mcp__aside__repl` plus the
  `Skill` tool for the skills bundled here (currently only 1Password). It's told
  to ask you before anything irreversible (purchases, sending messages,
  submitting forms, deleting).
- It may sign in to sites with the 1Password extension's autofill in the Aside
  Browser when a task needs a login. It never types secrets from chat and asks
  before autofilling payment cards.

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
| `/model` | Show the current model with buttons to switch; `/model <id>` switches directly |
| `/effort`| Show the current reasoning effort with buttons for the levels the model supports; `/effort <level>` sets it |

Messages sent while a task runs are queued and handled in order (one agent
turn per chat at a time). Conversations survive restarts: chat → session IDs
are stored in `.state/sessions.json` and resumed. Messages sent while the bot
was offline are dropped on startup, so stale commands don't run in your browser.

### Model and effort

The model list is not hardcoded: `/model` fetches it from Anthropic's
`GET /v1/models` with your `CLAUDE_CODE_OAUTH_TOKEN` (sent only to
api.anthropic.com), so new models appear on their own. Each model's supported
effort levels come from the same response, limited to the levels the installed
Agent SDK accepts. The list is cached for 24h in `.state/models_cache.json`; if
it can't be fetched, the last cached list is used, and with no list at all
`/model <id>` still accepts any `claude-...` id.

The choice is bot-wide and saved in `.state/settings.json` (defaults:
`ASIDE_BOT_MODEL` / `ASIDE_BOT_EFFORT`). A change applies from the next message
and keeps the conversation: the chat's agent is reconnected, resuming the same
session with the new `--model` / `--effort`. A task that is already running
finishes with the old setting. If the new model doesn't support the chosen
effort, the nearest lower supported level is used (or effort is omitted for
models without effort support), and the bot tells you.

## Layout

```
src/aside_telegram/
  agent.py       # Agent core (no Telegram): ClaudeSDKClient + aside MCP
  auth.py        # Subscription-only env for the Claude CLI subprocess
  config.py      # .env loading and validation
  models.py      # /v1/models discovery (model list, effort levels, cache)
  formatting.py  # 4096-char splitting, Markdown -> Telegram HTML
  bot.py         # Telegram handlers, per-chat locks, progress, photos
  plugin/        # Local Claude Code plugin carrying the agent's skills
    .claude-plugin/plugin.json
    skills/1password/SKILL.md
tests/           # pytest suite for the pure helpers
```

## Skills

The agent loads skills only from the bundled plugin in
`src/aside_telegram/plugin/` (passed to the CLI with `--plugin-dir`).
`setting_sources=[]` keeps your `~/.claude` settings, CLAUDE.md and personal
skills/plugins out, and `skills=["aside-telegram:1password"]` is the allowlist
of what the model sees and may invoke.

`skills/1password/SKILL.md` is a copy of Aside's builtin skill with two changes:
its `description` is rewritten so the agent reaches for it on any sign-in task,
not only when you say "1Password", and step 1 of the autofill flow says how to
click a menu item (`page.click('<ref>')`). To refresh it after an Aside update,
copy it and then restore those two edits:

```sh
cp ~/.aside/u/0/skills/builtin/1password/SKILL.md src/aside_telegram/plugin/skills/1password/
```

To add another Aside skill, copy its folder from `~/.aside/u/0/skills/builtin/`
into `src/aside_telegram/plugin/skills/` and add `aside-telegram:<name>` to
`SKILLS` in `agent.py`.

## Development

```sh
uv run pytest
```
