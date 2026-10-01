"""Anonim Chat Bot: tasodifiy suhbatdosh juftlash (xotirada, jarayon ichida)."""
from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter

from keyboards.inline import anon_menu

QUEUE: dict[int, list] = {}       # scope -> kutayotganlar
PAIRS: dict[tuple, int] = {}      # (scope, user) -> suhbatdosh


def build_anon_router() -> Router:
    r = Router()

    async def end_chat(bot, scope, uid, notify=True):
        partner = PAIRS.pop((scope, uid), None)
        if partner:
            PAIRS.pop((scope, partner), None)
            if notify:
                try:
                    await bot.send_message(partner, "⚠️ Suhbatdosh chatni tugatdi.", reply_markup=anon_menu())
                except TelegramAPIError:
                    pass
        QUEUE[scope] = [x for x in QUEUE.get(scope, []) if x != uid]

    async def find(c, bot, scope):
        uid = c.from_user.id
        if (scope, uid) in PAIRS:
            await c.answer("Siz allaqachon suhbatdasiz", show_alert=True)
            return
        q = [x for x in QUEUE.get(scope, []) if x != uid]
        if q:
            partner = q.pop(0)
            QUEUE[scope] = q
            PAIRS[(scope, uid)], PAIRS[(scope, partner)] = partner, uid
            txt = "✅ Suhbatdosh topildi! Yozing. Tugatish: ⏹"
            await c.message.answer(txt, reply_markup=anon_menu())
            try:
                await bot.send_message(partner, txt, reply_markup=anon_menu())
            except TelegramAPIError:
                await end_chat(bot, scope, uid, notify=False)
        else:
            QUEUE[scope] = q + [uid]
            await c.message.answer("🔍 Suhbatdosh qidirilmoqda... Topilganda xabar beraman.")
        await c.answer()

    @r.callback_query(F.data == "an:find")
    async def f(c, bot, scope):
        await find(c, bot, scope)

    @r.callback_query(F.data == "an:next")
    async def nxt(c, bot, scope):
        await end_chat(bot, scope, c.from_user.id)
        await find(c, bot, scope)

    @r.callback_query(F.data == "an:stop")
    async def stop(c, bot, scope):
        await end_chat(bot, scope, c.from_user.id)
        await c.message.answer("⏹ Chat tugatildi.", reply_markup=anon_menu())
        await c.answer()

    @r.message(StateFilter(None))
    async def relay(m, bot, scope):
        partner = PAIRS.get((scope, m.from_user.id))
        if not partner:
            if not (m.text or "").startswith("/"):
                await m.answer("🔍 Suhbatdosh topish uchun tugmani bosing:", reply_markup=anon_menu())
            return
        if (m.text or "").startswith("/"):
            return
        try:
            await m.copy_to(partner)  # matn, rasm, ovoz, stiker — hammasi anonim ko'chiriladi
        except TelegramAPIError:
            await end_chat(bot, scope, m.from_user.id, notify=False)
            await m.answer("⚠️ Suhbatdosh mavjud emas. Chat tugadi.", reply_markup=anon_menu())

    return r
