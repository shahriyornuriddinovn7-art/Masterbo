"""Barcha sozlamalar environment o'zgaruvchilaridan olinadi."""
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _ids(v: str) -> list[int]:
    return [int(x) for x in v.replace(" ", "").split(",") if x.strip("-").isdigit()]


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = _ids(os.getenv("ADMIN_IDS", ""))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/maker.db")
BASE_URL = os.getenv("BASE_URL") or os.getenv("RENDER_EXTERNAL_URL", "")  # bo'sh = polling
import hashlib
WEBHOOK_SECRET = hashlib.sha256(os.getenv("WEBHOOK_SECRET", "maker_secret_change_me").encode()).hexdigest()
PORT = int(os.getenv("PORT", "8080"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "dall-e-3")
AUDD_TOKEN = os.getenv("AUDD_TOKEN", "")
YTDLP_COOKIES = os.getenv("YTDLP_COOKIES", "")
TZ_OFFSET = int(os.getenv("TZ_OFFSET", "5"))  # O'zbekiston UTC+5

BOT_TYPES = {
    "kino": "🎬 Kodli Kino Bot",
    "music": "🎵 Musiqa Izlash Boti",
    "ai": "🤖 AI Chatbot",
    "logo": "🎨 AI Logo & Tasvir Bot",
    "edu": "🎓 Talaba va O'qituvchi Boti",
    "dl": "📥 Media Downloader Bot",
    "anon": "🕵️ Anonim Chat Bot",
}

WELCOME = {
    "kino": "🎬 <b>Kino bot</b>\n\nKino kodini yuboring — men videoni topib beraman.",
    "music": "🎵 <b>Musiqa izlash</b>\n\nQo'shiq/ijrochi nomini yozing yoki ovozli xabar / audio parcha yuboring.",
    "ai": "🤖 <b>AI yordamchi</b>\n\nSavolingizni yozing. Yangi suhbat: /new",
    "logo": "🎨 <b>AI Logo & Tasvir</b>\n\nKerakli logo yoki rasm tavsifini yozing.",
    "edu": "🎓 <b>Ta'lim yordamchisi</b>\n\nBo'limni tanlang:",
    "dl": "📥 <b>Media yuklovchi</b>\n\nInstagram / TikTok / YouTube Shorts havolasini yuboring.",
    "anon": "🕵️ <b>Anonim chat</b>\n\nSuhbatdosh topish uchun tugmani bosing.",
}
