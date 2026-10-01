"""AI Chatbot: OpenAI-mos API (kalit: bot egasi /admin → API kalit, yoki global)."""
from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, StateFilter

from services import AIError, NoKey, ask_ai
from utils import ad_suffix, esc, send_long

HIST: dict = {}
SYSTEM = "Sen foydali, do'stona AI yordamchisan. Foydalanuvchi qaysi tilda yozsa, shu tilda javob ber."


def build_ai_router() -> Router:
    r = Router()

    @r.message(Command("new"))
    async def new(m, scope):
        HIST.pop((scope, m.from_user.id), None)
        await m.answer("🧹 Yangi suhbat boshlandi.")

    @r.message(StateFilter(None), F.text)
    async def chat(m, bot, db, scope, admin_ids):
        if m.text.startswith("/"):
            return
        h = HIST.setdefault((scope, m.from_user.id), [])
        if len(HIST) > 5000:
            HIST.pop(next(iter(HIST)))
        h.append({"role": "user", "content": m.text[:4000]})
        del h[:-12]  # oxirgi 12 ta xabar kontekst
        await bot.send_chat_action(m.chat.id, ChatAction.TYPING)
        try:
            ans = await ask_ai(db, scope, [{"role": "system", "content": SYSTEM}] + h)
        except NoKey:
            h.pop()
            await m.answer("⚠️ Bot egasi hali AI API kalitini sozlamagan.")
            return
        except AIError as e:
            h.pop()
            await m.answer(f"⚠️ AI xatosi: {esc(str(e))[:300]}")
            return
        h.append({"role": "assistant", "content": ans})
        await send_long(m, ans)
        ad = await ad_suffix(db, admin_ids)
        if ad:
            await m.answer(ad.strip())

    return r
