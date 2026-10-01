"""Child bot admin paneli (bot egasi): kontent (kino, PDF), API kalit, salomlashuv matni."""
from aiogram import F, Router

from keyboards.inline import kb
from states import ChildSt
from utils import IsAdmin, esc, show

HOME = [("⬅️ Admin panel", "adm:home")]
CANCEL = kb([("❌ Bekor", "adm:home")])


def build_child_admin() -> Router:
    r = Router()
    r.message.filter(IsAdmin())
    r.callback_query.filter(IsAdmin())

    # ---------------- Salomlashuv ----------------
    @r.callback_query(F.data == "cb:welcome")
    async def w_ask(c, state):
        await state.set_state(ChildSt.welcome)
        await show(c, "👋 Yangi salomlashuv matnini yuboring (HTML mumkin). O'chirish uchun: <code>-</code>", CANCEL)
        await c.answer()

    @r.message(ChildSt.welcome, F.text)
    async def w_save(m, db, scope, state):
        if m.text.strip() == "-":
            await db.del_setting(scope, "welcome")
        else:
            await db.set_setting(scope, "welcome", m.text)
        await state.clear()
        await m.answer("✅ Saqlandi", reply_markup=kb(HOME))

    # ---------------- API kalit ----------------
    @r.callback_query(F.data == "cb:key")
    async def k_ask(c, state, bot_type):
        await state.set_state(ChildSt.api_key)
        hint = ("AudD tokenini yuboring (audio parcha aniqlash uchun)." if bot_type == "music" else
                "API kalitni yuboring:\n<code>KEY</code> yoki <code>KEY | BASE_URL | MODEL</code>\n"
                "Misol: <code>sk-... | https://api.openai.com/v1 | gpt-4o-mini</code>")
        await show(c, "🔑 " + hint + "\n\nO'chirish: <code>-</code>\n<i>Xabaringiz xavfsizlik uchun o'chiriladi.</i>", CANCEL)
        await c.answer()

    @r.message(ChildSt.api_key, F.text)
    async def k_save(m, db, scope, state):
        try:
            await m.delete()
        except Exception:
            pass
        t = m.text.strip()
        if t == "-":
            for k in ("api_key", "base_url", "model"):
                await db.del_setting(scope, k)
        else:
            parts = [p.strip() for p in t.split("|")]
            await db.set_setting(scope, "api_key", parts[0])
            if len(parts) > 1 and parts[1]:
                await db.set_setting(scope, "base_url", parts[1])
            if len(parts) > 2 and parts[2]:
                await db.set_setting(scope, "model", parts[2])
        await state.clear()
        await m.answer("✅ Kalit saqlandi", reply_markup=kb(HOME))

    # ---------------- Kino bazasi ----------------
    @r.callback_query(F.data == "cb:movie")
    async def movies(c, db, scope, state):
        await state.clear()
        rows = await db.fetch("SELECT code,title FROM movies WHERE scope=? ORDER BY title LIMIT 30", scope)
        btn = [[(f"🗑 {x['code']} — {x['title'][:30]}", f"cb:mdel:{x['code']}")] for x in rows]
        await show(c, f"🎬 <b>Kinolar bazasi</b> ({len(rows)} ta ko'rsatilmoqda)\n<i>O'chirish uchun bosing.</i>",
                   kb(*btn, [("➕ Kino qo'shish", "cb:madd")], HOME))
        await c.answer()

    @r.callback_query(F.data == "cb:madd")
    async def m_add(c, state):
        await state.set_state(ChildSt.movie_file)
        await show(c, "🎬 Video (yoki hujjat) faylni yuboring.", CANCEL)
        await c.answer()

    @r.message(ChildSt.movie_file, F.video | F.document)
    async def m_file(m, state):
        f, ft = (m.video, "video") if m.video else (m.document, "document")
        await state.update_data(file_id=f.file_id, ftype=ft, fname=(m.caption or getattr(f, "file_name", "") or "Kino"))
        await state.set_state(ChildSt.movie_code)
        await m.answer("🔑 Kod va nomni yuboring: <code>kod | Kino nomi</code>\nMasalan: <code>101 | Titanik (1997)</code>")

    @r.message(ChildSt.movie_code, F.text)
    async def m_code(m, db, scope, state):
        d = await state.get_data()
        code, _, title = m.text.partition("|")
        code, title = code.strip()[:30], (title.strip() or d.get("fname", "Kino"))
        if not code:
            await m.answer("Kod bo'sh bo'lmasin.")
            return
        await db.execute("INSERT INTO movies(scope,code,file_id,ftype,title) VALUES(?,?,?,?,?) "
                         "ON CONFLICT(scope,code) DO UPDATE SET file_id=excluded.file_id, ftype=excluded.ftype, title=excluded.title",
                         scope, code, d["file_id"], d["ftype"], title)
        await state.clear()
        await m.answer(f"✅ Saqlandi: <b>{esc(code)}</b> — {esc(title)}",
                       reply_markup=kb([("➕ Yana qo'shish", "cb:madd"), ("📋 Ro'yxat", "cb:movie")], HOME))

    @r.callback_query(F.data.startswith("cb:mdel:"))
    async def m_del(c, db, scope, state):
        await db.execute("DELETE FROM movies WHERE scope=? AND code=?", scope, c.data.split(":", 2)[2])
        await c.answer("🗑 O'chirildi")
        await movies(c, db, scope, state)

    # ---------------- PDF / darsliklar bazasi ----------------
    @r.callback_query(F.data == "cb:pdf")
    async def pdfs(c, db, scope, state):
        await state.clear()
        rows = await db.fetch("SELECT id,title FROM materials WHERE scope=? ORDER BY id DESC LIMIT 30", scope)
        btn = [[(f"🗑 {x['title'][:40]}", f"cb:pdel:{x['id']}")] for x in rows]
        await show(c, "📚 <b>Darsliklar bazasi</b>\n<i>O'chirish uchun bosing.</i>",
                   kb(*btn, [("➕ PDF qo'shish", "cb:padd")], HOME))
        await c.answer()

    @r.callback_query(F.data == "cb:padd")
    async def p_add(c, state):
        await state.set_state(ChildSt.pdf_file)
        await show(c, "📎 PDF/hujjatni yuboring (izohga sarlavha yozishingiz mumkin).", CANCEL)
        await c.answer()

    @r.message(ChildSt.pdf_file, F.document)
    async def p_save(m, db, scope, state):
        title = m.caption or m.document.file_name or "Material"
        await db.execute("INSERT INTO materials(scope,title,file_id) VALUES(?,?,?)", scope, title[:100], m.document.file_id)
        await state.clear()
        await m.answer(f"✅ Qo'shildi: {esc(title)}", reply_markup=kb([("➕ Yana", "cb:padd"), ("📋 Ro'yxat", "cb:pdf")], HOME))

    @r.callback_query(F.data.startswith("cb:pdel:"))
    async def p_del(c, db, scope, state):
        await db.execute("DELETE FROM materials WHERE scope=? AND id=?", scope, int(c.data.split(":")[2]))
        await c.answer("🗑 O'chirildi")
        await pdfs(c, db, scope, state)

    return r
