"""Barcha botlar uchun umumiy: /start, /cancel, obuna tekshirish (chk)."""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart

import config as cfg
from keyboards.inline import anon_menu, edu_home, maker_menu
from utils import check_subscriptions


def build_common_router() -> Router:
    r = Router()

    @r.message(CommandStart())
    async def start(m, state, db, scope, bot_type, admin_ids):
        await state.clear()
        await db.add_user(scope, m.from_user.id, m.from_user.full_name)
        is_admin = m.from_user.id in admin_ids
        if bot_type == "maker":
            await m.answer("👋 <b>Bot yaratuvchi (Maker Bot)</b>\n\nO'z Telegram botingizni bir necha daqiqada "
                           "yarating: Kino, Musiqa, AI, Logo, Ta'lim, Downloader yoki Anonim chat.",
                           reply_markup=maker_menu(is_admin))
            return
        text = await db.get_setting(scope, "welcome") or cfg.WELCOME[bot_type]
        if is_admin:
            text += "\n\n🛠 Admin panel: /admin"
        markup = edu_home(bot_type) if bot_type == "edu" else anon_menu() if bot_type == "anon" else None
        await m.answer(text, reply_markup=markup)

    @r.message(Command("cancel"))
    async def cancel(m, state):
        await state.clear()
        await m.answer("✅ Bekor qilindi. /start")

    @r.callback_query(F.data == "chk")
    async def chk(c, bot, db, scope):
        if await check_subscriptions(bot, db, scope, c.from_user.id):
            await c.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
            return
        await c.message.edit_text("✅ Rahmat! Obuna tasdiqlandi. Davom etish uchun /start ni bosing.")
        await c.answer()

    return r
