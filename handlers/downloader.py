"""Media Downloader: Instagram Reels / TikTok / YouTube Shorts havolasidan video yuklaydi."""
import os
import re

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import FSInputFile

from services import yt_download
from utils import ad_suffix

URL = re.compile(r"https?://(?:www\.|vm\.|vt\.|m\.)?(?:tiktok\.com|instagram\.com|youtube\.com|youtu\.be)/\S+", re.I)


def build_dl_router() -> Router:
    r = Router()

    @r.message(StateFilter(None), F.text)
    async def link(m, db, admin_ids):
        if m.text.startswith("/"):
            return
        mt = URL.search(m.text)
        if not mt:
            await m.answer("🔗 Instagram / TikTok / YouTube Shorts havolasini yuboring.")
            return
        wait = await m.answer("⏳ Yuklanmoqda...")
        path = None
        try:
            path, info = await yt_download(mt.group(0))
            await m.answer_video(FSInputFile(path), caption=(info.get("title") or "")[:200] + await ad_suffix(db, admin_ids))
            await wait.delete()
        except Exception:
            await wait.edit_text("❌ Yuklab bo'lmadi: havola yopiq/noto'g'ri yoki video 50MB dan katta.")
        finally:
            if path and os.path.exists(path):
                os.remove(path)

    return r
