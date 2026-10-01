"""Kodli Kino Bot: kod yuborilsa video qaytaradi."""
from aiogram import F, Router
from aiogram.filters import StateFilter

from utils import ad_suffix, esc


def build_kino_router() -> Router:
    r = Router()

    @r.message(StateFilter(None), F.text)
    async def by_code(m, db, scope, admin_ids):
        code = m.text.strip()
        if code.startswith("/"):
            return
        row = await db.fetchrow("SELECT * FROM movies WHERE scope=? AND code=?", scope, code)
        if not row:
            await m.answer("❌ Bunday kodli kino topilmadi. Kodni tekshirib qayta yuboring.")
            return
        cap = f"🎬 <b>{esc(row['title'])}</b>\n🔑 Kod: {esc(code)}" + await ad_suffix(db, admin_ids)
        send = m.answer_video if row["ftype"] == "video" else m.answer_document
        await send(row["file_id"], caption=cap)

    return r
