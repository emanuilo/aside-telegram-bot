"""Telegram text helpers: message splitting and Markdown -> Telegram HTML.

Telegram's HTML parse mode is much more forgiving than its MarkdownV2 mode
(only ``&``, ``<`` and ``>`` need escaping), so we convert the model's plain
Markdown into the small HTML subset Telegram supports. Callers should still
fall back to plain text if Telegram rejects the result.
"""

from __future__ import annotations

import html
import re

TELEGRAM_MAX_LEN = 4096
# Split the Markdown source below the hard limit so the HTML rendering
# (tags + entity escaping) still fits in one Telegram message.
SAFE_CHUNK_LEN = 3500

_FENCE = "```"


def split_message(text: str, limit: int = TELEGRAM_MAX_LEN) -> list[str]:
    """Split *text* into chunks of at most *limit* characters.

    Prefers paragraph breaks, then line breaks, then spaces; hard-cuts only
    when there is no whitespace. Code fences left open at a cut are closed in
    that chunk and reopened in the next one so each chunk renders on its own.
    """
    if limit < 16:
        raise ValueError("limit too small")
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    reopen = ""  # fence opener carried over from the previous chunk
    remaining = text
    while remaining:
        budget = limit - len(reopen)
        if len(remaining) <= budget:
            candidate = reopen + remaining
            if candidate.count(_FENCE) % 2 == 0 or len(candidate) + 4 > limit:
                chunks.append(candidate)
                break
            budget -= 4  # make room to close an unterminated fence
        else:
            budget -= 4  # we may need to append "\n```"
        cut = _find_cut(remaining, budget)
        piece = remaining[:cut].rstrip()
        remaining = remaining[cut:].lstrip("\n ")
        chunk = reopen + piece
        fence_open = chunk.count(_FENCE) % 2 == 1
        if fence_open:
            chunk += "\n" + _FENCE
            reopen = _last_fence_opener(chunk[: -len(_FENCE)]) + "\n"
        else:
            reopen = ""
        chunks.append(chunk)
        if not remaining:
            break
    return [c for c in chunks if c.strip()]


def _find_cut(text: str, budget: int) -> int:
    if len(text) <= budget:
        return len(text)
    window = text[:budget]
    for sep in ("\n\n", "\n", " "):
        idx = window.rfind(sep)
        if idx > budget // 3:
            return idx + len(sep)
    return budget


def _last_fence_opener(text: str) -> str:
    """Return the most recent opening fence line (e.g. "```python")."""
    opener = _FENCE
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(_FENCE):
            inside = not inside
            if inside:
                opener = stripped
    return opener


# ── Markdown -> Telegram HTML ───────────────────────────────────────

_CODE_BLOCK_RE = re.compile(r"```([\w+-]*)[ \t]*\n?(.*?)```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
_BOLD_RE = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", re.DOTALL)
_ITALIC_STAR_RE = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])")
_ITALIC_UNDER_RE = re.compile(r"(?<![\w_])_(?=\S)([^_\n]+?)(?<=\S)_(?![\w_])")
_STRIKE_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_HEADING_RE = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+(.+?)[ \t#]*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^([ \t]*)[*-][ \t]+", re.MULTILINE)


def markdown_to_telegram_html(text: str) -> str:
    """Convert common Markdown to Telegram-supported HTML."""
    placeholders: list[str] = []

    def stash(fragment: str) -> str:
        placeholders.append(fragment)
        return f"\x00{len(placeholders) - 1}\x00"

    def code_block(m: re.Match[str]) -> str:
        lang, body = m.group(1), m.group(2).rstrip("\n")
        cls = f' class="language-{lang}"' if lang else ""
        return stash(f"<pre><code{cls}>{html.escape(body, quote=False)}</code></pre>")

    out = _CODE_BLOCK_RE.sub(code_block, text)
    out = _INLINE_CODE_RE.sub(
        lambda m: stash(f"<code>{html.escape(m.group(1), quote=False)}</code>"), out
    )
    out = _LINK_RE.sub(
        lambda m: stash(
            f'<a href="{html.escape(m.group(2), quote=True)}">'
            f"{html.escape(m.group(1), quote=False)}</a>"
        ),
        out,
    )
    out = html.escape(out, quote=False)
    out = _HEADING_RE.sub(r"<b>\1</b>", out)
    out = _BULLET_RE.sub(r"\1• ", out)
    out = _BOLD_RE.sub(r"<b>\2</b>", out)
    out = _STRIKE_RE.sub(r"<s>\1</s>", out)
    out = _ITALIC_STAR_RE.sub(r"<i>\1</i>", out)
    out = _ITALIC_UNDER_RE.sub(r"<i>\1</i>", out)
    return re.sub(r"\x00(\d+)\x00", lambda m: placeholders[int(m.group(1))], out)
