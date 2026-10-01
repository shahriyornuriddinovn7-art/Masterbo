"""Musiqa Izlash Boti: nom bo'yicha qidirish (yt-dlp) va audio parchani aniqlash (AudD)."""
import os

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import FSInputFile

import config as cfg
from keyboards.inline import kb
from services import audd_recognize, yt_download, yt_search
from utils import ad_suffix, esc

CACHE: dict = {}  # (scope, video_id) -> telegram file_id


def _dur(s):
    s = int(s or 0)
    return f"{s // 60}:{s % 60:02d}"


def build_music_router() -> Router:
    r = Router()

    async def search(m, q):
        wait = await m.answer("🔎 Qidirilmoqda...")
        try:
            res = await yt_search(q)
        except Exception:
            res = []
        if not res:
            await wait.edit_text("😕 Hech narsa topilmadi.")
            return
        btn = [[(f"🎵 {e['title'][:48]} ({_dur(e.get('duration'))})", f"mu:{e['id']}")] for e in res]
        await wait.edit_text(f"🎶 <b>{esc(q)}</b> bo'yicha natijalar:", reply_markup=kb(*btn))

    @r.message(StateFilter(None), F.text)
    async def by_text(m):
        if not m.text.startswith("/") and len(m.text) > 1:
            await search(m, m.text[:100])

    @r.message(StateFilter(None), F.voice | F.audio | F.video_note)
    async def recognize(m, bot, db, scope):
        token = await db.get_setting(scope, "api_key") or cfg.AUDD_TOKEN
        if not token:
            await m.answer("⚠️ Audio aniqlash sozlanmagan (bot egasi AudD kalitini kiritmagan). Nom bilan qidiring.")
            return
        f = m.voice or m.audio or m.video_note
        if (f.file_size or 0) > 15 * 1024 * 1024:
            await m.answer("Fayl katta (15MB gacha).")
            return
        buf = await bot.download(f.file_id)
        try:
            title = await audd_recognize(token, buf.read())
        except Exception:
            title = None
        if not title:
            await m.answer("😕 Qo'shiq aniqlanmadi.")
            return
        await m.answer(f"✅ Aniqlandi: <b>{esc(title)}</b>")
        await search(m, title)

    @r.callback_query(F.data.startswith("mu:"))
    async def download(c, db, scope, admin_ids):
        vid = c.data[3:]
        await c.answer("⏳ Yuklanmoqda...")
        ad = await ad_suffix(db, admin_ids)
        if (scope, vid) in CACHE:
            await c.message.answer_audio(CACHE[(scope, vid)], caption=ad.strip() or None)
            return
        wait = await c.message.answer("⏳ Yuklab olinmoqda, kuting...")
        path = None
        try:
            path, info = await yt_download(f"https://www.youtube.com/watch?v={vid}", audio=True)
            sent = await c.message.answer_audio(FSInputFile(path), title=(info.get("title") or "")[:64],
                                                performer=info.get("uploader"), duration=int(info.get("duration") or 0),
                                                caption=ad.strip() or None)
            CACHE[(scope, vid)] = sent.audio.file_id
            await wait.delete()
        except Exception:
            await wait.edit_text("❌ Yuklab bo'lmadi (fayl katta yoki mavjud emas).")
        finally:
            if path and os.path.exists(path):
                os.remove(path)

    return r
