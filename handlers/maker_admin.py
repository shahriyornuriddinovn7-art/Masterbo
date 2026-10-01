"""Faqat Maker bot adminiga: yaratilgan botlarni boshqarish, reklama va premium."""
import time

from aiogram import F, Router
from aiogram.filters import Command

import config as cfg
from keyboards.inline import kb
from states import MakerSt
from utils import IsAdmin, esc, show

ICON = {"active": "🟢", "inactive": "⚪️", "blocked": "🚫", "invalid": "⚠️"}
HOME = [("⬅️ Admin panel", "adm:home")]


def build_maker_admin() -> Router:
    r = Router()
    r.message.filter(IsAdmin())
    r.callback_query.filter(IsAdmin())

    @r.message(Command("diag"))
    async def diag(m, db, manager):
        rows = await db.fetch("SELECT id,username,type,status FROM bots ORDER BY id DESC LIMIT 15")
        total = await db.fetchval("SELECT COUNT(*) FROM bots")
        lines = []
        for x in rows:
            item = manager.by_scope.get(x["id"])
            wh = ""
            if item and cfg.BASE_URL:
                try:
                    wh = " | " + ((await item.bot.get_webhook_info()).last_error_message or "webhook ok")[:50]
                except Exception as e:
                    wh = " | " + str(e)[:40]
            err = manager.errors.get(x["id"], "")
            lines.append(f"#{x['id']} @{x['username']} [{x['type']}] {x['status']} — "
                         f"{'✅ ishlayapti' if item else '❌ ishlamayapti'}{wh} {err[:80]}")
        await m.answer(f"🩺 <b>Diagnostika</b>\nBaza: {'PostgreSQL ✅' if db.pg else 'SQLite ⚠️ (Render\'da o`chib ketadi!)'}\n"
                       f"Rejim: {'webhook' if cfg.BASE_URL else 'polling'}\nBazada botlar: {total} | Ishlayotgan: {len(manager.by_scope) - 1}\n\n"
                       + esc("\n".join(lines)))

    @r.callback_query(F.data == "ma:bots")
    async def bots(c, db):
        rows = await db.fetch("SELECT * FROM bots ORDER BY id DESC LIMIT 40")
        btn = [[(f"{ICON.get(x['status'], '❔')} #{x['id']} @{x['username']} [{x['type']}]", f"ma:bot:{x['id']}")] for x in rows]
        await show(c, f"🤖 <b>Yaratilgan botlar</b> (oxirgi {len(rows)} ta)", kb(*btn, HOME))
        await c.answer()

    async def detail(c, db, bid):
        x = await db.fetchrow("SELECT * FROM bots WHERE id=?", bid)
        if not x:
            await c.answer("Topilmadi", show_alert=True)
            return
        users = await db.fetchval("SELECT COUNT(*) FROM users WHERE scope=?", bid)
        text = (f"🤖 <b>@{esc(x['username'] or '')}</b> (#{bid})\nTuri: {cfg.BOT_TYPES.get(x['type'])}\n"
                f"Egasi: <code>{x['owner_id']}</code>\nHolat: {ICON.get(x['status'])} {x['status']}\n"
                f"Foydalanuvchilar: {users}\nToken: <code>{x['token'][:8]}…</code>")
        await show(c, text, kb(
            [("⚪️ Noaktiv qilish" if x["status"] == "active" else "🟢 Aktiv qilish", f"ma:tog:{bid}")],
            [("✅ Blokdan chiqarish" if x["status"] == "blocked" else "🚫 Bloklash", f"ma:blk:{bid}")],
            [("🗑 Tokenni o'chirish", f"ma:del:{bid}")], [("⬅️ Ro'yxat", "ma:bots")]))
        await c.answer()

    @r.callback_query(F.data.startswith("ma:bot:"))
    async def bot_detail(c, db):
        await detail(c, db, int(c.data.split(":")[2]))

    async def set_status(c, db, manager, bid, status):
        await db.execute("UPDATE bots SET status=? WHERE id=?", status, bid)
        if status == "active":
            row = await db.fetchrow("SELECT * FROM bots WHERE id=?", bid)
            if not await manager.start_child(row):
                await db.execute("UPDATE bots SET status='invalid' WHERE id=?", bid)
        else:
            await manager.stop(bid)
        await detail(c, db, bid)

    @r.callback_query(F.data.startswith("ma:tog:"))
    async def tog(c, db, manager):
        bid = int(c.data.split(":")[2])
        st = await db.fetchval("SELECT status FROM bots WHERE id=?", bid)
        if st == "blocked":
            await c.answer("Avval blokdan chiqaring", show_alert=True)
            return
        await set_status(c, db, manager, bid, "inactive" if st == "active" else "active")

    @r.callback_query(F.data.startswith("ma:blk:"))
    async def blk(c, db, manager):
        bid = int(c.data.split(":")[2])
        st = await db.fetchval("SELECT status FROM bots WHERE id=?", bid)
        await set_status(c, db, manager, bid, "active" if st == "blocked" else "blocked")

    @r.callback_query(F.data.startswith("ma:del:"))
    async def delete(c, db, manager):
        await manager.remove(int(c.data.split(":")[2]))
        await c.answer("🗑 Bot va token o'chirildi")
        await bots(c, db)

    # ---------------- Reklama va Premium ----------------
    async def ads_view(event, db):
        ad = await db.get_setting(0, "ad_text")
        free = await db.get_setting(0, "max_bots", 3)
        prem = await db.get_setting(0, "prem_bots", 20)
        await show(event, f"💰 <b>Reklama va Premium</b>\n\n📢 Reklama: {esc(ad) if ad else 'o`chirilgan'}\n"
                          f"🔢 Bepul bot limiti: <b>{free}</b>\n💎 Premium limiti: <b>{prem}</b>\n\n"
                          "<i>Reklama yaratilgan botlarda javoblar ostida chiqadi. Premium egalar reklamasiz.</i>",
                   kb([("✏️ Reklama matni", "ma:adtxt"), ("🚫 Reklamani o'chirish", "ma:adoff")],
                      [("🔢 Limitlar", "ma:lim"), ("💎 Premium berish", "ma:prem")], HOME))

    @r.callback_query(F.data == "ma:ads")
    async def ads(c, db, state):
        await state.clear()
        await ads_view(c, db)
        await c.answer()

    @r.callback_query(F.data == "ma:adoff")
    async def ad_off(c, db):
        await db.del_setting(0, "ad_text")
        await ads_view(c, db)
        await c.answer("O'chirildi")

    @r.callback_query(F.data.in_({"ma:adtxt", "ma:lim", "ma:prem"}))
    async def ask(c, state):
        st, hint = {"ma:adtxt": (MakerSt.ad_text, "Reklama matnini yuboring:"),
                    "ma:lim": (MakerSt.limit, "Limitlarni yuboring: <code>bepul premium</code> (masalan: <code>3 20</code>)"),
                    "ma:prem": (MakerSt.premium, "<code>user_id kunlar</code> yuboring (masalan: <code>12345 30</code>; 0 = bekor)")}[c.data]
        await state.set_state(st)
        await show(c, hint, kb([("❌ Bekor", "ma:ads")]))
        await c.answer()

    @r.message(MakerSt.ad_text, F.text)
    async def s_ad(m, db, state):
        await db.set_setting(0, "ad_text", m.text[:300])
        await state.clear()
        await ads_view(m, db)

    @r.message(MakerSt.limit, F.text)
    async def s_lim(m, db, state):
        try:
            a, b = [int(x) for x in m.text.split()[:2]]
        except ValueError:
            await m.answer("Format: <code>3 20</code>")
            return
        await db.set_setting(0, "max_bots", a)
        await db.set_setting(0, "prem_bots", b)
        await state.clear()
        await ads_view(m, db)

    @r.message(MakerSt.premium, F.text)
    async def s_prem(m, db, state):
        try:
            uid, days = [int(x) for x in m.text.split()[:2]]
        except ValueError:
            await m.answer("Format: <code>12345 30</code>")
            return
        until = int(time.time()) + days * 86400 if days > 0 else 0
        await db.execute("INSERT INTO premium(user_id,until) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET until=excluded.until",
                         uid, until)
        await state.clear()
        await m.answer(f"💎 {uid} uchun premium: {days} kun")
        await ads_view(m, db)

    return r
