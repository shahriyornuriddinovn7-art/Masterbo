"""Maker bot foydalanuvchi qismi: bot yaratish va o'z botlarini boshqarish."""
import re
import time

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError

import config as cfg
from keyboards.inline import kb, maker_menu, types_kb
from states import MakerSt
from utils import esc, show


def build_maker_router() -> Router:
    r = Router()

    @r.callback_query(F.data == "mk:home")
    async def home(c, state, admin_ids):
        await state.clear()
        await show(c, "🏠 <b>Bosh menyu</b>", maker_menu(c.from_user.id in admin_ids))
        await c.answer()

    @r.callback_query(F.data == "mk:new")
    async def new(c, db, state, admin_ids):
        await state.clear()
        uid = c.from_user.id
        free = int(await db.get_setting(0, "max_bots", 3))
        prem = int(await db.get_setting(0, "prem_bots", 20))
        limit = 999 if uid in admin_ids else (prem if await db.is_premium(uid) else free)
        cnt = await db.fetchval("SELECT COUNT(*) FROM bots WHERE owner_id=?", uid)
        if cnt >= limit:
            await c.answer(f"❌ Limit: {limit} ta bot. Ko'proq uchun Premium oling.", show_alert=True)
            return
        await show(c, "🤖 Qanday bot yaratmoqchisiz?", types_kb())
        await c.answer()

    @r.callback_query(F.data.startswith("mk:type:"))
    async def pick(c, state):
        t = c.data.split(":")[2]
        await state.set_state(MakerSt.token)
        await state.update_data(type=t)
        await show(c, f"{cfg.BOT_TYPES[t]}\n\n1️⃣ @BotFather ga kiring → /newbot\n2️⃣ Olingan <b>tokenni</b> shu yerga yuboring.",
                   kb([("⬅️ Orqaga", "mk:new")]))
        await c.answer()

    @r.message(MakerSt.token, F.text)
    async def got_token(m, state, db, manager):
        token = m.text.strip()
        try:
            await m.delete()  # tokenni chatda qoldirmaymiz
        except TelegramAPIError:
            pass
        if not re.fullmatch(r"\d{6,12}:[\w-]{30,50}", token):
            await m.answer("❌ Token formati noto'g'ri. Qayta yuboring yoki /cancel.")
            return
        if await db.fetchval("SELECT id FROM bots WHERE token=?", token):
            await m.answer("❌ Bu token allaqachon ulangan.")
            return
        tmp = Bot(token)
        try:
            me = await tmp.get_me()
        except TelegramAPIError:
            await m.answer("❌ Token yaroqsiz. Tekshirib qayta yuboring.")
            return
        finally:
            await tmp.session.close()
        t = (await state.get_data())["type"]
        await state.clear()
        bid = await db.fetchval(
            "INSERT INTO bots(owner_id,token,username,bot_id,type,status,created_at) VALUES(?,?,?,?,?,?,?) RETURNING id",
            m.from_user.id, token, me.username, me.id, t, "active", int(time.time()))
        row = await db.fetchrow("SELECT * FROM bots WHERE id=?", bid)
        ok = await manager.start_child(row)
        if ok:
            await m.answer(f"✅ <b>Tayyor!</b> @{me.username} ishga tushdi.\n\nBotingizga kirib /admin yuboring — "
                           f"u yerda statistika, obuna, xabar yuborish va kontent boshqaruvi bor.",
                           reply_markup=kb([("🚀 Botni ochish", f"https://t.me/{me.username}")], [("🏠 Menyu", "mk:home")]))
        else:
            err = esc(manager.errors.get(bid, "noma'lum"))[:300]
            await m.answer(f"⚠️ Bot saqlandi, lekin ishga tushmadi.\n<code>{err}</code>")

    # ---------------- Mening botlarim ----------------
    @r.callback_query(F.data == "mk:my")
    async def my(c, db):
        rows = await db.fetch("SELECT * FROM bots WHERE owner_id=? ORDER BY id", c.from_user.id)
        btn = [[(f"@{x['username']} — {x['type']}", f"mk:b:{x['id']}")] for x in rows]
        await show(c, "🤖 <b>Mening botlarim</b>" + ("" if rows else "\n\nHali bot yaratmagansiz."),
                   kb(*btn, [("➕ Yangi bot", "mk:new")], [("⬅️ Orqaga", "mk:home")]))
        await c.answer()

    async def own(c, db, bid):
        x = await db.fetchrow("SELECT * FROM bots WHERE id=? AND owner_id=?", bid, c.from_user.id)
        if not x:
            await c.answer("Topilmadi", show_alert=True)
        return x

    @r.callback_query(F.data.startswith("mk:b:"))
    async def detail(c, db):
        x = await own(c, db, int(c.data.split(":")[2]))
        if x:
            users = await db.fetchval("SELECT COUNT(*) FROM users WHERE scope=?", x["id"])
            await show(c, f"🤖 <b>@{esc(x['username'] or '')}</b>\nTuri: {cfg.BOT_TYPES.get(x['type'])}\n"
                          f"Holat: {x['status']}\nFoydalanuvchilar: {users}\n\nBoshqarish: botda /admin",
                       kb([("🚀 Ochish", f"https://t.me/{x['username']}")],
                          [("🗑 O'chirish", f"mk:bdel:{x['id']}")], [("⬅️ Orqaga", "mk:my")]))
            await c.answer()

    @r.callback_query(F.data.startswith("mk:bdel:"))
    async def del_ask(c, db):
        x = await own(c, db, int(c.data.split(":")[2]))
        if x:
            await show(c, "⚠️ Bot va uning barcha ma'lumotlari o'chiriladi. Ishonchingiz komilmi?",
                       kb([("✅ Ha, o'chirish", f"mk:bdok:{x['id']}"), ("❌ Yo'q", f"mk:b:{x['id']}")]))
            await c.answer()

    @r.callback_query(F.data.startswith("mk:bdok:"))
    async def del_ok(c, db, manager):
        x = await own(c, db, int(c.data.split(":")[2]))
        if x:
            await manager.remove(x["id"])
            await c.answer("🗑 O'chirildi")
            await my(c, db)

    return r
