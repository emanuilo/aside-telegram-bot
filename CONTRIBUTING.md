# Contributing to aside-telegram

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

You need [uv](https://docs.astral.sh/uv/). It installs the right Python for you.

```bash
git clone https://github.com/emanuilo/aside-telegram-bot.git
cd aside-telegram-bot
uv sync
```

To run the bot itself you also need macOS, the Aside Browser with its CLI, a
Claude subscription and a Telegram bot (see the [README](README.md#quickstart)).
Copy the environment template and fill it in:

```bash
cp .env.example .env
```

Use a separate test bot from @BotFather for development, not the one you use
day to day.

## Running Tests

```bash
uv run pytest
```

All tests should pass before submitting a PR. The suite needs no tokens,
network, Aside or Telegram: Telegram objects, the agent and the model API are
faked. To check another Python version:

```bash
uv run --python 3.10 pytest
```

## Code Style

Formatting and linting use [Ruff](https://docs.astral.sh/ruff/) (configured in
`pyproject.toml`, line length 100):

```bash
uv run ruff check        # lint (add --fix for safe autofixes)
uv run ruff format       # format
```

CI runs `ruff check`, `ruff format --check` and `pytest` on Python 3.10–3.14.

- Use type hints for function signatures
- Keep functions focused and small
- Keep `agent.py` free of Telegram code so the agent core stays scriptable
- Never log tokens or request headers

## Making Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Add or update tests as needed
5. Run the checks above
6. Commit with a clear message (`git commit -m 'feat: add my feature'`)
7. Push to your fork (`git push origin feature/my-feature`)
8. Open a Pull Request

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) style:

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation only
- `test:` adding or updating tests
- `chore:` maintenance, dependencies, CI

## Pull Requests

- Keep PRs focused on a single change
- Include tests for new functionality
- Update the README, `docs/` and `CHANGELOG.md` if behavior or configuration changes
- Link related issues in the PR description

## Skills

Skills we write live in `src/aside_telegram/plugin/skills/` and are MIT
licensed like the rest of the code. Don't copy Aside's builtin skills into the
repo: they are loaded from the user's local Aside install at startup (see
`ASIDE_SKILLS` in `src/aside_telegram/skills.py`).

## Reporting Bugs

Open an issue with:

- Steps to reproduce
- Expected vs actual behavior
- macOS, Python and Aside versions
- Relevant logs (remove tokens, user IDs and private page content first)

Security issues: please follow [SECURITY.md](SECURITY.md) instead of opening a
public issue.

## Questions?

Open an [issue](https://github.com/emanuilo/aside-telegram-bot/issues).
