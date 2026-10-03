"""Telegram layer: routes allowlisted chats to per-chat BrowsingAgent sessions."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from loguru import logger
from telegram import LinkPreviewOptions, Message, ReplyParameters, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .agent import BrowsingAgent, Image, ToolStep, TurnResult, instructions_fingerprint
from .config import Settings
from .formatting import SAFE_CHUNK_LEN, TELEGRAM_MAX_LEN, markdown_to_telegram_html, split_message

MAX_PHOTOS_PER_TURN = 5
STATUS_EDIT_INTERVAL_S = 2.0
TYPING_INTERVAL_S = 4.0
_NO_PREVIEW = LinkPreviewOptions(is_disabled=True)

HELP_TEXT = (
    "I'm a browsing assistant driving your Aside browser.\n\n"
    "Just tell me what to do, e.g. \"open example.com and tell me the heading\".\n\n"
    "/new - start a fresh conversation\n"
    "/stop - interrupt the current task (and drop queued messages)\n\n"
    "I'll ask before doing anything irreversible (purchases, sending messages, "
    "submitting forms, deleting)."
)


# ── Session persistence ─────────────────────────────────────────────


class SessionStore:
    """chat_id -> Claude session id, persisted so restarts keep context.

    Each entry also records the fingerprint of the agent instructions the
    session was started with; Claude Code keeps a session's original system
    prompt on resume, so entries from other instructions aren't resumed.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, dict[str, str]] = {}
        try:
            raw = json.loads(path.read_text())
        except FileNotFoundError:
            raw = {}
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable session store {}: {}", path, exc)
            raw = {}
        for key, value in raw.items():
            # Legacy entries were bare session ids with no fingerprint.
            self._data[key] = value if isinstance(value, dict) else {"session_id": value}

    def get(self, chat_id: int, fingerprint: str) -> str | None:
        """The session to resume, or None if there is none or it is stale."""
        entry = self._data.get(str(chat_id))
        if entry and entry.get("fingerprint") == fingerprint:
            return entry.get("session_id")
        return None

    def has(self, chat_id: int) -> bool:
        return str(chat_id) in self._data

    def set(self, chat_id: int, session_id: str | None, fingerprint: str = "") -> None:
        key = str(chat_id)
        if session_id:
            entry = {"session_id": session_id, "fingerprint": fingerprint}
            if self._data.get(key) == entry:
                return
            self._data[key] = entry
        elif self._data.pop(key, None) is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.replace(self.path)


# ── Per-chat state ──────────────────────────────────────────────────


@dataclass
class ChatState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    agent: BrowsingAgent | None = None
    # Bumped by /stop and /new so messages queued before them are dropped.
    epoch: int = 0


class AsideBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.state_dir = settings.state_file.parent.resolve()
        self.sessions = SessionStore(settings.state_file)
        self.chats: dict[int, ChatState] = {}
        self.fingerprint = instructions_fingerprint()

    def _chat(self, chat_id: int) -> ChatState:
        return self.chats.setdefault(chat_id, ChatState())

    def _new_agent(self, chat_id: int) -> tuple[BrowsingAgent, bool]:
        """Create the chat's agent. The flag is True if a saved session was
        dropped because the agent's instructions changed since it started."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        # Fixed cwd so Claude Code stores/resumes sessions in one place.
        cfg = replace(self.settings.agent, cwd=self.state_dir)
        resume = self.sessions.get(chat_id, self.fingerprint)
        stale = resume is None and self.sessions.has(chat_id)
        if stale:
            logger.info("Instructions changed; not resuming the old session for chat {}", chat_id)
            self.sessions.set(chat_id, None)
        return BrowsingAgent(cfg, resume=resume), stale

    # -- application -----------------------------------------------------

    def build_application(self) -> Application:
        app = (
            ApplicationBuilder()
            .token(self.settings.telegram_bot_token)
            # Needed so /stop can run while a message handler is busy.
            .concurrent_updates(True)
            .post_shutdown(self._post_shutdown)
            .build()
        )
        allowed = filters.User(user_id=list(self.settings.allowed_user_ids))
        app.add_handler(CommandHandler(["start", "help"], self.cmd_start, filters=allowed))
        app.add_handler(CommandHandler("new", self.cmd_new, filters=allowed))
        app.add_handler(CommandHandler("stop", self.cmd_stop, filters=allowed))
        app.add_handler(MessageHandler(allowed & filters.TEXT & ~filters.COMMAND, self.on_text))
        # Everyone else (and unsupported message types) lands here.
        app.add_handler(MessageHandler(filters.ALL, self.on_other))
        app.add_error_handler(self.on_error)
        return app

    async def _post_shutdown(self, app: Application) -> None:
        for state in self.chats.values():
            if state.agent is not None:
                await state.agent.close()

    # -- handlers ----------------------------------------------------------

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(HELP_TEXT)

    async def cmd_new(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        state = self._chat(chat_id)
        state.epoch += 1
        if state.lock.locked() and state.agent is not None:
            with contextlib.suppress(Exception):
                await state.agent.interrupt()
        async with state.lock:
            if state.agent is not None:
                await state.agent.close()
                state.agent = None
            self.sessions.set(chat_id, None)
        await update.effective_message.reply_text("Started a new conversation.")

    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        state = self._chat(update.effective_chat.id)
        state.epoch += 1
        if not state.lock.locked() or state.agent is None:
            await update.effective_message.reply_text("Nothing is running.")
            return
        try:
            await state.agent.interrupt()
            await update.effective_message.reply_text("Stopping the current task…")
        except Exception as exc:  # noqa: BLE001
            logger.exception("interrupt failed")
            await update.effective_message.reply_text(f"Couldn't interrupt: {exc}")

    async def on_other(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        msg = update.effective_message
        if user is None or user.id not in self.settings.allowed_user_ids:
            logger.warning(
                "Rejected update from user id={} username={}",
                user.id if user else None, user.username if user else None,
            )
            if msg is not None and update.effective_chat and update.effective_chat.type == "private":
                await msg.reply_text(
                    f"Sorry, you're not allowed to use this bot. (Your user id: {user.id if user else '?'})"
                )
            return
        if msg is not None:
            await msg.reply_text("I can only handle text messages for now.")

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        chat_id = update.effective_chat.id
        state = self._chat(chat_id)
        epoch = state.epoch
        if state.lock.locked():
            await msg.reply_text("Queued; I'll get to it after the current task. (/stop to cancel)")
        async with state.lock:
            if state.epoch != epoch:
                logger.info("Dropping message queued before /stop or /new in chat {}", chat_id)
                return
            await self._run_turn(context, msg, state, chat_id)

    async def on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.opt(exception=context.error).error("Unhandled error while processing an update")

    # -- turn ------------------------------------------------------------

    async def _run_turn(
        self, context: ContextTypes.DEFAULT_TYPE, msg: Message, state: ChatState, chat_id: int
    ) -> None:
        bot = context.bot
        if state.agent is None:
            state.agent, stale = self._new_agent(chat_id)
            if stale:
                await self._send_text(
                    bot, chat_id, "My instructions were updated, so this is a fresh conversation."
                )
        agent = state.agent

        typing = asyncio.create_task(self._keep_typing(bot, chat_id))
        status: Message | None = None
        last_edit = 0.0

        async def on_tool(step: ToolStep) -> None:
            nonlocal status, last_edit
            now = time.monotonic()
            if now - last_edit < STATUS_EDIT_INTERVAL_S:
                return
            last_edit = now
            text = f"Working… step {step.index}: {step.summary}"
            try:
                if status is None:
                    status = await bot.send_message(chat_id, text, disable_notification=True)
                else:
                    await status.edit_text(text)
            except TelegramError as exc:
                logger.debug("status update failed: {}", exc)

        try:
            result = await agent.ask(msg.text, on_tool=on_tool)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent turn failed in chat {}", chat_id)
            # The CLI subprocess may be dead; reconnect (resuming) next time.
            if agent.session_id:
                self.sessions.set(chat_id, agent.session_id, self.fingerprint)
            await agent.close()
            state.agent = None
            await self._send_text(bot, chat_id, f"Sorry, something went wrong: {exc}", reply_to=msg)
            return
        finally:
            typing.cancel()
            if status is not None:
                with contextlib.suppress(TelegramError):
                    await status.delete()

        if result.session_id:
            self.sessions.set(chat_id, result.session_id, self.fingerprint)
        await self._deliver(bot, chat_id, msg, result)

    async def _deliver(self, bot, chat_id: int, msg: Message, result: TurnResult) -> None:
        text = result.text.strip()
        if result.interrupted:
            text = (text + "\n\n" if text else "") + "(stopped)"
        elif result.is_error:
            detail = "; ".join(result.errors) or "unknown error"
            text = (text + "\n\n" if text else "") + f"(The agent hit an error: {detail})"
        if not text and not result.images:
            text = "(no reply)"
        if text:
            await self._send_text(bot, chat_id, text, reply_to=msg)
        for image in result.images[-MAX_PHOTOS_PER_TURN:]:
            await self._send_image(bot, chat_id, image)

    async def _send_text(self, bot, chat_id: int, text: str, reply_to: Message | None = None) -> None:
        for i, chunk in enumerate(split_message(text, SAFE_CHUNK_LEN)):
            reply = (
                ReplyParameters(reply_to.message_id, allow_sending_without_reply=True)
                if (reply_to is not None and i == 0) else None
            )
            html_text = markdown_to_telegram_html(chunk)
            if len(html_text) <= TELEGRAM_MAX_LEN:
                try:
                    await bot.send_message(
                        chat_id, html_text, parse_mode=ParseMode.HTML,
                        reply_parameters=reply, link_preview_options=_NO_PREVIEW,
                    )
                    continue
                except BadRequest as exc:
                    logger.debug("HTML send rejected ({}); falling back to plain text", exc)
            await bot.send_message(
                chat_id, chunk, reply_parameters=reply, link_preview_options=_NO_PREVIEW
            )

    async def _send_image(self, bot, chat_id: int, image: Image) -> None:
        ext = image.media_type.split("/")[-1] or "png"
        try:
            await bot.send_photo(chat_id, io.BytesIO(image.data), filename=f"screenshot.{ext}")
        except TelegramError as exc:
            # Too large / odd dimensions for a photo: fall back to a document.
            logger.debug("send_photo failed ({}); sending as document", exc)
            with contextlib.suppress(TelegramError):
                await bot.send_document(chat_id, io.BytesIO(image.data), filename=f"screenshot.{ext}")

    @staticmethod
    async def _keep_typing(bot, chat_id: int) -> None:
        while True:
            with contextlib.suppress(TelegramError):
                await bot.send_chat_action(chat_id, ChatAction.TYPING)
            await asyncio.sleep(TYPING_INTERVAL_S)
