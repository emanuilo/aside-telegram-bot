"""Subscription-only auth for the Claude Code CLI subprocess.

The Agent SDK shells out to the Claude Code CLI and *merges* ``options.env``
over the parent process environment, so passing a scrubbed dict alone is not
enough to keep a stray ``ANTHROPIC_API_KEY`` out of the subprocess. We therefore
(1) remove credential vars from ``os.environ`` of this (dedicated) bot process
and (2) pass an explicit env that contains at most ``CLAUDE_CODE_OAUTH_TOKEN``.

Billing therefore always goes through the user's Claude subscription:
- ``oauth_token``  -> CLAUDE_CODE_OAUTH_TOKEN from ``claude setup-token``
- ``local_login``  -> no token; the CLI uses the local Claude Code login
An API key is never injected.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, MutableMapping

# Every env var that could make the CLI authenticate with something other
# than the subscription token we inject (or route billing elsewhere).
SCRUBBED_ENV_VARS: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
)

AUTH_MODE_OAUTH = "oauth_token"
AUTH_MODE_LOCAL = "local_login"


def scrub_env(env: Mapping[str, str]) -> dict[str, str]:
    """Return a copy of *env* without any credential / provider-routing vars."""
    return {k: v for k, v in env.items() if k not in SCRUBBED_ENV_VARS}


def scrub_process_env(environ: MutableMapping[str, str] | None = None) -> list[str]:
    """Remove credential vars from the live process env (default ``os.environ``).

    Needed because the SDK merges ``options.env`` *over* ``os.environ``.
    Returns the names that were removed (values are never returned/logged).
    """
    environ = os.environ if environ is None else environ
    removed = [k for k in SCRUBBED_ENV_VARS if k in environ]
    for k in removed:
        del environ[k]
    return removed


def build_cli_env(
    oauth_token: str | None, base_env: Mapping[str, str] | None = None
) -> tuple[dict[str, str], str]:
    """Build the env for the Claude CLI subprocess.

    Scrubs every credential var from *base_env* (default ``os.environ``) and
    injects only ``CLAUDE_CODE_OAUTH_TOKEN`` if one is configured. Never
    injects ``ANTHROPIC_API_KEY``.

    Returns ``(env, auth_mode)``.
    """
    env = scrub_env(os.environ if base_env is None else base_env)
    token = (oauth_token or "").strip()
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        return env, AUTH_MODE_OAUTH
    return env, AUTH_MODE_LOCAL
