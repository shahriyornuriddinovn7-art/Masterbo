"""AI Logo & Tasvir generatori."""
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import BufferedInputFile

from keyboards.inline import kb
from services import AIError, generate_image
from states import LogoSt
from utils import ad_suffix, esc

STYLES = {
    "logo": "Professional minimalist vector logo, flat design, clean shapes, white background: ",
    "photo": "Ultra realistic high quality photo, detailed, cinematic lighting: ",
    "illu": "Beautiful digital illustration, vibrant colors, detailed: ",
    "3d": "3D render, glossy, studio lighting, high detail: ",
}


def build_logo_router() -> Router:
    r = Router()

    @r.message(StateFilter(None), F.text)
    async def prompt(m, state):
        if m.text.startswith("/"):
            return
        await state.update_data(prompt=m.text[:800])
        await state.set_state(LogoSt.style)
        await m.answer("🎨 Uslubni tanlang:", reply_markup=kb(
            [("🏷 Logo", "lg:logo"), ("🖼 Rasm", "lg:photo")], [("✏️ Illustratsiya", "lg:illu"), ("🧊 3D", "lg:3d")]))

    @r.callback_query(LogoSt.style, F.data.startswith("lg:"))
    async def gen(c, state, db, scope, admin_ids):
        d = await state.get_data()
        await state.clear()
        await c.message.edit_text("⏳ Yaratilmoqda (10–40 soniya)...")
        try:
            img = await generate_image(db, scope, STYLES[c.data[3:]] + d["prompt"])
        except AIError as e:
            await c.message.edit_text(f"⚠️ Xato: {esc(str(e))[:200]}")
            return
        await c.message.answer_photo(BufferedInputFile(img, "image.png"),
                                     caption="✅ Tayyor!" + await ad_suffix(db, admin_ids))
        await c.answer()

    @r.callback_query(F.data.startswith("lg:"))
    async def stale(c):
        await c.answer("Sessiya tugagan, tavsifni qayta yozing.", show_alert=True)

    return r
