"""Maker va child botlar uchun UMUMIY admin panel: statistika, majburiy obuna, broadcast."""
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

import config as cfg
from keyboards.inline import admin_home, kb
from states import AdminSt
from utils import IsAdmin, broadcast, esc, show, spawn

HOME = [("⬅️ Admin panel", "adm:home")]


async def stats_text(db, scope, bot_type) -> str:
    users = await db.fetchval("SELECT COUNT(*) FROM users WHERE scope=?", scope)
    blocked = await db.fetchval("SELECT COUNT(*) FROM users WHERE scope=? AND blocked=1", scope)
    if bot_type == "maker":
        rows = await db.fetch("SELECT type, status, COUNT(*) c FROM bots GROUP BY type, status")
        total = sum(x["c"] for x in rows)
        lines = []
        for k, label in cfg.BOT_TYPES.items():
            t = sum(x["c"] for x in rows if x["type"] == k)
            a = sum(x["c"] for x in rows if x["type"] == k and x["status"] == "active")
            lines.append(f"{label}: <b>{t}</b> (aktiv: {a})")
        return (f"📊 <b>Maker statistikasi</b>\n\n👥 Foydalanuvchilar: <b>{users}</b> (bloklagan: {blocked})\n"
                f"🤖 Jami botlar: <b>{total}</b>\n\n" + "\n".join(lines))
    extra = ""
    if bot_type == "kino":
        extra = f"\n🎬 Kinolar: <b>{await db.fetchval('SELECT COUNT(*) FROM movies WHERE scope=?', scope)}</b>"
    if bot_type == "edu":
        extra = f"\n📚 PDF materiallar: <b>{await db.fetchval('SELECT COUNT(*) FROM materials WHERE scope=?', scope)}</b>"
    return f"📊 <b>Bot statistikasi</b>\n\n👥 Foydalanuvchilar: <b>{users}</b> (bloklagan: {blocked}){extra}"


def build_shared_admin() -> Router:
    r = Router()
    r.message.filter(IsAdmin())
    r.callback_query.filter(IsAdmin())

    @r.message(Command("admin"))
    async def admin_cmd(m, state, bot_type):
        await state.clear()
        await m.answer("🛠 <b>Admin panel</b>", reply_markup=admin_home(bot_type))

    @r.callback_query(F.data == "adm:home")
    async def home(c, state, bot_type):
        await state.clear()
        await show(c, "🛠 <b>Admin panel</b>", admin_home(bot_type))
        await c.answer()

    @r.callback_query(F.data == "adm:stats")
    async def stats(c, db, scope, bot_type):
        await show(c, await stats_text(db, scope, bot_type), kb(HOME))
        await c.answer()

    # ---------------- Majburiy obuna ----------------
    @r.callback_query(F.data == "adm:ch")
    async def channels(c, db, scope, state):
        await state.clear()
        rows = await db.fetch("SELECT * FROM channels WHERE scope=?", scope)
        buttons = [[(f"🗑 {x['title']}", f"adm:chdel:{x['id']}")] for x in rows]
        buttons += [[("➕ Kanal qo'shish", "adm:chadd"), ("✅ Tekshirish", "adm:chchk")], HOME]
        text = "📢 <b>Majburiy obuna kanallari</b>\n\n" + ("\n".join(f"• {esc(x['title'])}" for x in rows) or "Kanal yo'q.")
        await show(c, text + "\n\n<i>Kanalni o'chirish uchun nomini bosing.</i>", kb(*buttons))
        await c.answer()

    @r.callback_query(F.data == "adm:chadd")
    async def ch_add(c, state):
        await state.set_state(AdminSt.add_channel)
        await show(c, "Kanal <b>@username</b> yoki ID (-100...) yuboring, yoki kanaldan xabar forward qiling.\n"
                      "⚠️ Bot avval kanalga <b>admin</b> qilinishi shart.", kb([("❌ Bekor", "adm:ch")]))
        await c.answer()

    @r.message(AdminSt.add_channel)
    async def ch_save(m: Message, state, bot, db, scope):
        ref = None
        if m.forward_origin and m.forward_origin.type == "channel":
            ref = m.forward_origin.chat.id
        elif m.text:
            t = m.text.strip().replace("https://t.me/", "@")
            ref = int(t) if re.fullmatch(r"-?\d+", t) else (t if t.startswith("@") else "@" + t)
        try:
            chat = await bot.get_chat(ref)
            me = await bot.get_chat_member(chat.id, bot.id)
            if me.status not in ("administrator", "creator"):
                await m.answer("❌ Bot bu kanalda admin emas. Avval admin qiling va qayta yuboring.")
                return
            link = f"https://t.me/{chat.username}" if chat.username else (
                chat.invite_link or await bot.export_chat_invite_link(chat.id))
        except Exception as e:
            await m.answer(f"❌ Kanal topilmadi: {esc(str(e))[:200]}")
            return
        if await db.fetchval("SELECT id FROM channels WHERE scope=? AND ref=?", scope, str(chat.id)):
            await m.answer("Bu kanal allaqachon qo'shilgan.")
        else:
            await db.execute("INSERT INTO channels(scope,ref,title,link) VALUES(?,?,?,?)",
                             scope, str(chat.id), chat.title or str(chat.id), link)
            await m.answer(f"✅ Qo'shildi: <b>{esc(chat.title or '')}</b>")
        await state.clear()
        await m.answer("📢 Majburiy obuna", reply_markup=kb([("📋 Ro'yxat", "adm:ch")], HOME))

    @r.callback_query(F.data.startswith("adm:chdel:"))
    async def ch_del(c, db, scope, state):
        await db.execute("DELETE FROM channels WHERE scope=? AND id=?", scope, int(c.data.split(":")[2]))
        await c.answer("🗑 O'chirildi")
        await channels(c, db, scope, state)

    @r.callback_query(F.data == "adm:chchk")
    async def ch_check(c, bot, db, scope):
        rows = await db.fetch("SELECT * FROM channels WHERE scope=?", scope)
        lines = []
        for x in rows:
            try:
                me = await bot.get_chat_member(int(x["ref"]), bot.id)
                ok = me.status in ("administrator", "creator")
            except Exception:
                ok = False
            lines.append(f"{'✅' if ok else '❌'} {esc(x['title'])}" + ("" if ok else " — bot admin emas"))
        await show(c, "🔎 <b>Tekshiruv natijasi</b>\n\n" + ("\n".join(lines) or "Kanal yo'q."),
                   kb([("📋 Ro'yxat", "adm:ch")], HOME))
        await c.answer()

    # ---------------- Broadcast ----------------
    @r.callback_query(F.data == "adm:bc")
    async def bc_start(c, state):
        await state.set_state(AdminSt.bc_msg)
        await show(c, "✉️ Yuboriladigan xabarni jo'nating (matn, rasm, video, ...).", kb([("❌ Bekor", "adm:home")]))
        await c.answer()

    @r.message(AdminSt.bc_msg)
    async def bc_msg(m: Message, state):
        await state.update_data(src_chat=m.chat.id, src_msg=m.message_id)
        await state.set_state(AdminSt.bc_btn)
        await m.answer("Inline tugma qo'shish uchun har qatorga:\n<code>Matn - https://link.uz</code>\n"
                       "yuboring yoki /skip.")

    @r.message(AdminSt.bc_btn)
    async def bc_btn(m: Message, state, bot):
        btns = []
        if (m.text or "").strip() != "/skip":
            for line in (m.text or "").splitlines():
                mt = re.match(r"^(.+?)\s*[-|]\s*(https?://\S+)$", line.strip())
                if mt:
                    btns.append([mt.group(1), mt.group(2)])
        await state.update_data(btns=btns)
        d = await state.get_data()
        markup = kb(*[[tuple(b)] for b in btns]) if btns else None
        await m.answer("👀 Oldindan ko'rish:")
        await bot.copy_message(m.chat.id, d["src_chat"], d["src_msg"], reply_markup=markup)
        await m.answer("Yuborish rejimini tanlang:", reply_markup=kb(
            [("✅ Oddiy (copy)", "adm:bcgo:copy"), ("↪️ Forward", "adm:bcgo:forward")], [("❌ Bekor", "adm:home")]))

    @r.callback_query(F.data.startswith("adm:bcgo:"))
    async def bc_go(c, state, bot, db, scope):
        d = await state.get_data()
        await state.clear()
        if "src_msg" not in d:
            await c.answer("Sessiya tugagan, qayta boshlang", show_alert=True)
            return
        mode = c.data.split(":")[2]
        markup = kb(*[[tuple(b)] for b in d.get("btns", [])]) if d.get("btns") else None
        admin_id = c.from_user.id

        async def job():
            ok, fail = await broadcast(bot, db, scope, d["src_chat"], d["src_msg"], mode, markup)
            await bot.send_message(admin_id, f"✅ Yuborildi: <b>{ok}</b>\n❌ Xato/bloklagan: <b>{fail}</b>")
        spawn(job())
        await show(c, "🚀 Xabar yuborish boshlandi. Tugagach hisobot keladi.", kb(HOME))
        await c.answer()

    return r
