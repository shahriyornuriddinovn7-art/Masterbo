# Maker Bot (aiogram 3 + aiohttp + SQLite/PostgreSQL)

## Ishga tushirish
**Lokal:** `pip install -r requirements.txt`, `.env.example` → `.env`, `python main.py` (BASE_URL bo'sh = polling).
**Render:** GitHub'ga push → New → Blueprint (`render.yaml`) → `BOT_TOKEN`, `ADMIN_IDS`, `OPENAI_API_KEY` ni kiriting.
Free web service 15 daqiqa so'rovsiz uxlaydi: UptimeRobot bilan `https://<app>.onrender.com/` ni har 5 daqiqada ping qiling.
Doimiy ma'lumot uchun PostgreSQL (`DATABASE_URL`) ishlating; Render diskida SQLite redeploy'da o'chadi.

## Struktura
main.py (server + start) · runtime.py (ko'p botli webhook/polling) · database.py · services.py (AI, yt-dlp, docx/pptx)
handlers/: common, shared_admin, maker, maker_admin, child_admin, kino, music, ai_chat, logo, edu, downloader, anon
keyboards/inline.py

## ⚠️ Render'da MAJBURIY: PostgreSQL
Render bepul tarifida disk vaqtinchalik: SQLite fayli har deploy va uyg'onishda o'chadi, yaratilgan botlar yo'qoladi.
1. Render → New → PostgreSQL (Free) → **Internal Database URL** ni nusxalang.
2. Web Service → Environment → `DATABASE_URL` = shu URL.
3. Botda `/diag` (faqat admin) — baza turi va har bir child bot holatini ko'rsatadi.
