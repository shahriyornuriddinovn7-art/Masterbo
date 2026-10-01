"""Umumiy yordamchilar: xabar ko'rsatish, obuna tekshirish, broadcast, middleware, filterlar."""
import asyncio
import logging
import time
from html import escape as esc

from aiogram import BaseMiddleware
from aiogram.exceptions import (TelegramAPIError, TelegramBadRequest, TelegramForbiddenError,
                                TelegramRetryAfter)
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message, TelegramObject

from keyboards.inline import join_kb, kb

log = logging.getLogger("utils")
BG: set = set()
NOPREVIEW = LinkPreviewOptions(is_disabled=True)


def spawn(coro):
    """Fon vazifasi (referensni ushlab turadi)."""
    t = asyncio.create_task(coro)
    BG.add(t)

    def done(task):
        BG.discard(task)
        if not task.cancelled() and task.exception():
            log.error("Fon vazifasi xatosi", exc_info=task.exception())
    t.add_done_callback(done)
    return t


async def show(event, text, markup=None):
    """CallbackQuery bo'lsa xabarni tahrirlaydi, Message bo'lsa yangi xabar yuboradi."""
    try:
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=markup, link_preview_options=NOPREVIEW)
        else:
            await event.answer(text, reply_markup=markup, link_preview_options=NOPREVIEW)
    except TelegramBadRequest as e:
        if "not modified" in str(e):
            return
        msg = event.message if isinstance(event, CallbackQuery) else event
        await msg.answer(text, reply_markup=markup)


async def send_long(m: Message, text: str):
    """Uzun matnni bo'lib yuboradi (HTML-xavfsiz)."""
    for i in range(0, len(text), 3000):
        await m.answer(esc(text[i:i + 3000]))


async def ad_suffix(db, admin_ids) -> str:
    """Maker admini qo'ygan reklama (premium egalarga ko'rsatilmaydi)."""
    ad = await db.get_setting(0, "ad_text")
    if not ad or (admin_ids and await db.is_premium(admin_ids[0])):
        return ""
    return "\n\n📢 " + ad


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, admin_ids: list) -> bool:
        u = getattr(event, "from_user", None)
        return bool(u and u.id in admin_ids)


async def check_subscriptions(bot, db, scope, user_id):
    """Foydalanuvchi obuna bo'lmagan kanallar ro'yxatini qaytaradi."""
    missing = []
    for ch in await db.fetch("SELECT * FROM channels WHERE scope=?", scope):
        try:
            m = await bot.get_chat_member(int(ch["ref"]), user_id)
            if m.status in ("left", "kicked") or (m.status == "restricted" and not getattr(m, "is_member", True)):
                missing.append(ch)
        except TelegramAPIError:
            continue  # bot kanalda admin emas — foydalanuvchini bloklamaymiz
    return missing


class SubscriptionMiddleware(BaseMiddleware):
    """Har bir xabar/callback oldidan majburiy obunani tekshiradi (admin va 'chk' tugmasi bundan mustasno)."""

    def __init__(self, db):
        self.db = db
        self.cache: dict = {}

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if not user or user.id in data["admin_ids"] or (isinstance(event, CallbackQuery) and event.data == "chk"):
            return await handler(event, data)
        msg = event.message if isinstance(event, CallbackQuery) else event
        if msg is None or msg.chat.type != "private":
            return await handler(event, data)
        key = (data["scope"], user.id)
        if self.cache.get(key, 0) > time.time():
            return await handler(event, data)
        missing = await check_subscriptions(data["bot"], self.db, data["scope"], user.id)
        if not missing:
            self.cache[key] = time.time() + 120
            return await handler(event, data)
        await self.db.add_user(data["scope"], user.id, user.full_name)
        if len(self.cache) > 20000:
            self.cache.clear()
        await msg.answer("📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=join_kb(missing))
        if isinstance(event, CallbackQuery):
            await event.answer()


async def broadcast(bot, db, scope, src_chat, src_msg, mode, markup):
    """Barcha foydalanuvchilarga yuboradi. mode: 'copy' | 'forward'. (ok, fail) qaytaradi."""
    ok = fail = 0
    for u in await db.fetch("SELECT user_id FROM users WHERE scope=? AND blocked=0", scope):
        uid = u["user_id"]
        for _ in range(2):
            try:
                if mode == "forward":
                    await bot.forward_message(uid, src_chat, src_msg)
                else:
                    await bot.copy_message(uid, src_chat, src_msg, reply_markup=markup)
                ok += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except TelegramForbiddenError:
                await db.execute("UPDATE users SET blocked=1 WHERE scope=? AND user_id=?", scope, uid)
                fail += 1
                break
            except TelegramAPIError:
                fail += 1
                break
        await asyncio.sleep(0.04)  # ~25 xabar/soniya — Telegram limiti ichida
    return ok, fail
