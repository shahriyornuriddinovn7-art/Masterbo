"""Talabalar va O'qituvchilar bo'limi (Maker botda ham, 'edu' turidagi child botda ham ishlaydi)."""
import re
import time
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.types import BufferedInputFile

import config as cfg
from keyboards.inline import edu_home, kb
from services import AIError, NoKey, ask_ai, extract_json, make_docx, make_pptx
from states import EduSt
from utils import esc, send_long, show

DAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
SYS = "Sen tajribali o'qituvchi va akademik yordamchisan. Aniq, tuzilgan, xatosiz yoz. Til so'ralmasa — o'zbek tilida."
PROMPTS = {
    "referat": "Quyidagi mavzuda REFERAT yoz: reja, kirish, 3-4 bob (har biri batafsil), xulosa, foydalanilgan adabiyotlar. "
               "Sarlavhalar uchun Markdown (#, ##) ishlat.\nMavzu: {t}",
    "kurs": "KURS ISHI yoz: mundarija, kirish (dolzarblik, maqsad, vazifalar, ob'yekt), 2-3 bob (har biri 2-3 paragraf), "
            "xulosa, adabiyotlar. Markdown sarlavhalar ishlat.\nMavzu: {t}",
    "slayd": 'Taqdimot uchun 8-10 ta slayd tayyorla. FAQAT JSON qaytar: [{{"title":"..","bullets":["..","..",".."]}}]\nMavzu: {t}',
    "plan": "O'qituvchi uchun DARS ISHLANMASI (konspekt) tuz: maqsad va vazifalar, jihozlar, bosqichlar (vaqt bilan), "
            "yangi mavzu bayoni, mustahkamlash savollari, uyga vazifa, baholash. Markdown sarlavhalar ishlat.\nMa'lumot: {t}",
}
QUIZ = ('Mavzu bo\'yicha {n} ta test savoli tuz. FAQAT JSON qaytar: [{{"q":"savol","options":["A","B","C","D"],'
        '"answer":0,"explanation":"qisqa izoh"}}] (answer — to\'g\'ri variant indeksi 0-3).\nMavzu: {t}')


def build_edu_router() -> Router:
    r = Router()
    BACK_ST, BACK_TE = [("⬅️ Ortga", "edu:st")], [("⬅️ Ortga", "edu:te")]

    @r.callback_query(F.data == "edu:home")
    async def home(c, state, bot_type):
        await state.clear()
        await show(c, "🎓 <b>Talabalar va O'qituvchilar uchun</b>", edu_home(bot_type))
        await c.answer()

    @r.callback_query(F.data == "edu:st")
    async def st(c, state):
        await state.clear()
        await show(c, "🎒 <b>Talabalar uchun</b>", kb(
            [("📅 Dars jadvali", "edu:sch")], [("⏰ Eslatmalar", "edu:rem")],
            [("📝 Referat / Slayd / Kurs ishi", "edu:gen")], [("📚 Darsliklar va PDF", "edu:lib")],
            [("⬅️ Ortga", "edu:home")]))
        await c.answer()

    @r.callback_query(F.data == "edu:te")
    async def te(c, state):
        await state.clear()
        await show(c, "👨‍🏫 <b>O'qituvchilar uchun</b>", kb(
            [("🧪 Test tuzuvchi (Quiz)", "edu:quiz")], [("👥 O'quvchilar va davomat", "edu:stu")],
            [("📖 Dars ishlanmasi (AI)", "edu:plan")], [("⬅️ Ortga", "edu:home")]))
        await c.answer()

    # ================= Dars jadvali =================
    @r.callback_query(F.data == "edu:sch")
    async def sch(c, db, scope, state):
        await state.clear()
        rows = await db.fetch("SELECT * FROM schedule WHERE scope=? AND user_id=? ORDER BY id", scope, c.from_user.id)
        by = {}
        for x in rows:
            by.setdefault(x["day"], []).append(x["line"])
        body = "\n\n".join(f"<b>{d}</b>\n" + "\n".join("• " + esc(l) for l in by[d]) for d in DAYS if d in by)
        await show(c, "📅 <b>Dars jadvali</b>\n\n" + (body or "Hozircha bo'sh."), kb(
            [("➕ Dars qo'shish", "edu:sch_add"), ("🗑 Tozalash", "edu:sch_clr")], BACK_ST))
        await c.answer()

    @r.callback_query(F.data == "edu:sch_add")
    async def sch_add(c, state):
        await state.set_state(EduSt.sch_add)
        await show(c, "Format: <code>Dushanba 09:00 Matematika, 305-xona</code>", kb([("❌ Bekor", "edu:sch")]))
        await c.answer()

    @r.message(EduSt.sch_add, F.text)
    async def sch_save(m, db, scope, state):
        parts = m.text.split(None, 1)
        day = next((d for d in DAYS if len(parts) == 2 and d.lower().startswith(parts[0].lower()[:3])), None)
        if not day:
            await m.answer("❌ Hafta kunini boshida yozing. Masalan: <code>Juma 10:30 Fizika</code>")
            return
        await db.execute("INSERT INTO schedule(scope,user_id,day,line) VALUES(?,?,?,?)", scope, m.from_user.id, day, parts[1][:200])
        await m.answer("✅ Qo'shildi. Yana yuboring yoki /cancel.", reply_markup=kb([("📅 Jadval", "edu:sch")]))

    @r.callback_query(F.data == "edu:sch_clr")
    async def sch_clr(c, db, scope, state):
        await db.execute("DELETE FROM schedule WHERE scope=? AND user_id=?", scope, c.from_user.id)
        await sch(c, db, scope, state)

    # ================= Eslatmalar =================
    @r.callback_query(F.data == "edu:rem")
    async def rem(c, db, scope, state):
        await state.clear()
        rows = await db.fetch("SELECT * FROM reminders WHERE scope=? AND user_id=? AND done=0 ORDER BY due LIMIT 15", scope, c.from_user.id)
        tz = timezone(timedelta(hours=cfg.TZ_OFFSET))
        lines = [f"• {datetime.fromtimestamp(x['due'], tz):%d.%m %H:%M} — {esc(x['text'])}" for x in rows]
        await show(c, "⏰ <b>Eslatmalar</b>\n\n" + ("\n".join(lines) or "Yaqin eslatma yo'q."), kb(
            [("➕ Eslatma qo'shish", "edu:rem_add"), ("🗑 Tozalash", "edu:rem_clr")], BACK_ST))
        await c.answer()

    @r.callback_query(F.data == "edu:rem_add")
    async def rem_add(c, state):
        await state.set_state(EduSt.rem_add)
        await show(c, "Format: <code>05.10 09:00 Fizika labaratoriya topshirish</code>", kb([("❌ Bekor", "edu:rem")]))
        await c.answer()

    @r.message(EduSt.rem_add, F.text)
    async def rem_save(m, db, scope, state):
        mt = re.match(r"^(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})\s+(.+)$", m.text.strip(), re.S)
        if not mt:
            await m.answer("❌ Format noto'g'ri. Masalan: <code>05.10 09:00 Matn</code>")
            return
        d, mo, h, mi = map(int, mt.groups()[:4])
        tz = timezone(timedelta(hours=cfg.TZ_OFFSET))
        now = datetime.now(tz)
        try:
            due = datetime(now.year, mo, d, h, mi, tzinfo=tz)
            if due < now:
                due = due.replace(year=now.year + 1)
        except ValueError:
            await m.answer("❌ Sana noto'g'ri.")
            return
        await db.execute("INSERT INTO reminders(scope,user_id,text,due,done) VALUES(?,?,?,?,0)",
                         scope, m.from_user.id, mt.group(5)[:300], int(due.timestamp()))
        await state.clear()
        await m.answer("✅ Eslatma qo'yildi!", reply_markup=kb([("⏰ Eslatmalar", "edu:rem")]))

    @r.callback_query(F.data == "edu:rem_clr")
    async def rem_clr(c, db, scope, state):
        await db.execute("UPDATE reminders SET done=1 WHERE scope=? AND user_id=?", scope, c.from_user.id)
        await rem(c, db, scope, state)

    # ================= Kutubxona =================
    @r.callback_query(F.data == "edu:lib")
    async def lib(c, db, scope):
        rows = await db.fetch("SELECT id,title FROM materials WHERE scope=? ORDER BY id DESC LIMIT 30", scope)
        btn = [[(f"📄 {x['title'][:45]}", f"edu:get:{x['id']}")] for x in rows]
        await show(c, "📚 <b>Darsliklar va PDF materiallar</b>" + ("" if rows else "\n\nHozircha bo'sh."), kb(*btn, BACK_ST))
        await c.answer()

    @r.callback_query(F.data.startswith("edu:get:"))
    async def get(c, db, scope):
        x = await db.fetchrow("SELECT * FROM materials WHERE scope=? AND id=?", scope, int(c.data.split(":")[2]))
        if x:
            await c.message.answer_document(x["file_id"], caption=esc(x["title"]))
        await c.answer()

    # ================= AI generatsiya (referat/kurs/slayd/konspekt) =================
    @r.callback_query(F.data == "edu:gen")
    async def gen_menu(c):
        await show(c, "📝 Nimani tayyorlaymiz?", kb(
            [("📄 Referat", "edu:g:referat"), ("📘 Kurs ishi", "edu:g:kurs")], [("📊 Slayd (PPTX)", "edu:g:slayd")], BACK_ST))
        await c.answer()

    @r.callback_query(F.data.startswith("edu:g:"))
    async def gen_pick(c, state):
        await state.set_state(EduSt.gen_topic)
        await state.update_data(kind=c.data.split(":")[2])
        await show(c, "✍️ Mavzuni yozing (xohlasangiz til/hajmni ham ko'rsating).", kb([("❌ Bekor", "edu:gen")]))
        await c.answer()

    @r.callback_query(F.data == "edu:plan")
    async def plan_ask(c, state):
        await state.set_state(EduSt.plan_topic)
        await state.update_data(kind="plan")
        await show(c, "📖 Fan, sinf/kurs va mavzuni yozing.\nMasalan: <i>Informatika, 8-sinf, Algoritm tushunchasi, 45 daqiqa</i>",
                   kb([("❌ Bekor", "edu:te")]))
        await c.answer()

    @r.message(EduSt.gen_topic, F.text)
    @r.message(EduSt.plan_topic, F.text)
    async def generate(m, state, db, scope):
        d = await state.get_data()
        kind, topic = d.get("kind", "referat"), m.text.strip()[:500]
        await state.clear()
        wait = await m.answer("⏳ Tayyorlanmoqda, 20–60 soniya kuting...")
        try:
            text = await ask_ai(db, scope, [{"role": "system", "content": SYS},
                                            {"role": "user", "content": PROMPTS[kind].format(t=topic)}], max_tokens=4000)
        except NoKey:
            await wait.edit_text("⚠️ AI API kaliti sozlanmagan (admin: /admin → API kalit).")
            return
        except AIError as e:
            await wait.edit_text(f"⚠️ AI xatosi: {esc(str(e))[:250]}")
            return
        await wait.delete()
        name = re.sub(r"\W+", "_", topic)[:30] or "file"
        try:
            if kind == "slayd":
                data = make_pptx(topic, extract_json(text))
                await m.answer_document(BufferedInputFile(data, f"{name}.pptx"), caption="📊 Slayd tayyor")
            else:
                await m.answer_document(BufferedInputFile(make_docx(topic, text), f"{name}.docx"), caption="✅ Tayyor (Word)")
                if len(text) <= 3000:
                    await send_long(m, text)
        except Exception:
            await send_long(m, text)  # fayl yasalmasa — matn ko'rinishida

    # ================= Test tuzuvchi =================
    @r.callback_query(F.data == "edu:quiz")
    async def quiz_ask(c, state):
        await state.set_state(EduSt.quiz_topic)
        await show(c, "🧪 Mavzu va savollar sonini yozing:\n<code>Fotosintez | 5</code>", kb([("❌ Bekor", "edu:te")]))
        await c.answer()

    @r.message(EduSt.quiz_topic, F.text)
    async def quiz_make(m, state, bot, db, scope):
        mt = re.match(r"^(.+?)\s*[|,]\s*(\d{1,2})$", m.text.strip())
        topic, n = (mt.group(1), min(int(mt.group(2)), 15)) if mt else (m.text.strip(), 5)
        await state.clear()
        wait = await m.answer("⏳ Test tuzilmoqda...")
        try:
            items = extract_json(await ask_ai(db, scope, [{"role": "system", "content": SYS},
                                                           {"role": "user", "content": QUIZ.format(n=n, t=topic)}]))
        except NoKey:
            await wait.edit_text("⚠️ AI API kaliti sozlanmagan.")
            return
        except Exception:
            await wait.edit_text("⚠️ Test tuzib bo'lmadi, qayta urinib ko'ring.")
            return
        if isinstance(items, dict):
            items = next((v for v in items.values() if isinstance(v, list)), [])
        await wait.edit_text(f"✅ <b>{esc(topic)}</b> bo'yicha test. Quyidagi savollarni o'quvchilarga forward qiling:")
        for q in items:
            try:
                opts = [str(o)[:100] for o in q["options"][:4]]
                await bot.send_poll(m.chat.id, str(q["q"])[:300], opts, type="quiz", is_anonymous=False,
                                    correct_option_id=int(q["answer"]), explanation=(q.get("explanation") or "")[:200] or None)
            except Exception:
                continue

    # ================= O'quvchilar va davomat =================
    async def students(c, db, scope):
        return await db.fetch("SELECT id,name FROM students WHERE scope=? AND teacher_id=? ORDER BY name LIMIT 40", scope, c.from_user.id)

    @r.callback_query(F.data == "edu:stu")
    async def stu(c, db, scope, state):
        await state.clear()
        rows = await students(c, db, scope)
        text = "👥 <b>O'quvchilar ro'yxati</b>\n\n" + ("\n".join(f"{i}. {esc(x['name'])}" for i, x in enumerate(rows, 1)) or "Hozircha bo'sh.")
        await show(c, text, kb([("➕ Qo'shish", "edu:stu_add"), ("🗑 Tozalash", "edu:stu_clr")],
                               [("📋 Davomat olish", "edu:att"), ("📈 Hisobot", "edu:rep")], BACK_TE))
        await c.answer()

    @r.callback_query(F.data == "edu:stu_add")
    async def stu_add(c, state):
        await state.set_state(EduSt.stu_add)
        await show(c, "O'quvchilar ismini yuboring (har qatorda bittadan).", kb([("❌ Bekor", "edu:stu")]))
        await c.answer()

    @r.message(EduSt.stu_add, F.text)
    async def stu_save(m, db, scope, state):
        names = [n.strip()[:60] for n in m.text.splitlines() if n.strip()][:60]
        for n in names:
            await db.execute("INSERT INTO students(scope,teacher_id,name) VALUES(?,?,?)", scope, m.from_user.id, n)
        await state.clear()
        await m.answer(f"✅ {len(names)} ta o'quvchi qo'shildi.", reply_markup=kb([("👥 Ro'yxat", "edu:stu")]))

    @r.callback_query(F.data == "edu:stu_clr")
    async def stu_clr(c, db, scope, state):
        await db.execute("DELETE FROM attendance WHERE student_id IN (SELECT id FROM students WHERE scope=? AND teacher_id=?)", scope, c.from_user.id)
        await db.execute("DELETE FROM students WHERE scope=? AND teacher_id=?", scope, c.from_user.id)
        await stu(c, db, scope, state)

    def att_kb(rows, absent):
        b = [[(("❌ " if x["id"] in absent else "✅ ") + x["name"], f"edu:at:{x['id']}")] for x in rows]
        return kb(*b, [("💾 Saqlash", "edu:atsave")], [("⬅️ Ortga", "edu:stu")])

    @r.callback_query(F.data == "edu:att")
    async def att(c, db, scope, state):
        rows = await students(c, db, scope)
        if not rows:
            await c.answer("Avval o'quvchilarni qo'shing", show_alert=True)
            return
        await state.update_data(absent=[])
        await show(c, "📋 <b>Davomat</b> — kelmaganlarni ❌ qiling, so'ng saqlang:", att_kb(rows, set()))
        await c.answer()

    @r.callback_query(F.data.startswith("edu:at:"))
    async def att_toggle(c, db, scope, state):
        sid = int(c.data.split(":")[2])
        ab = set((await state.get_data()).get("absent", []))
        ab ^= {sid}
        await state.update_data(absent=list(ab))
        await c.message.edit_reply_markup(reply_markup=att_kb(await students(c, db, scope), ab))
        await c.answer()

    @r.callback_query(F.data == "edu:atsave")
    async def att_save(c, db, scope, state):
        ab = set((await state.get_data()).get("absent", []))
        day = (datetime.now(timezone.utc) + timedelta(hours=cfg.TZ_OFFSET)).strftime("%Y-%m-%d")
        rows = await students(c, db, scope)
        for x in rows:
            await db.execute("DELETE FROM attendance WHERE student_id=? AND day=?", x["id"], day)
            await db.execute("INSERT INTO attendance(student_id,day,present) VALUES(?,?,?)", x["id"], day, 0 if x["id"] in ab else 1)
        await state.update_data(absent=[])
        await show(c, f"✅ {day} davomati saqlandi. Kelmaganlar: {len(ab)} ta.", kb([("📈 Hisobot", "edu:rep")], BACK_TE))
        await c.answer()

    @r.callback_query(F.data == "edu:rep")
    async def report(c, db, scope):
        lines = []
        for x in await students(c, db, scope):
            t = await db.fetchval("SELECT COUNT(*) FROM attendance WHERE student_id=?", x["id"])
            p = await db.fetchval("SELECT COALESCE(SUM(present),0) FROM attendance WHERE student_id=?", x["id"])
            lines.append(f"• {esc(x['name'])} — {p}/{t}" + (f" ({p * 100 // t}%)" if t else ""))
        await show(c, "📈 <b>Davomat hisoboti</b>\n\n" + ("\n".join(lines) or "Ma'lumot yo'q."), kb([("⬅️ Ortga", "edu:stu")]))
        await c.answer()

    return r
