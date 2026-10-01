"""Barcha inline klaviaturalar. Qator formati: [(matn, callback_data yoki https://url), ...]"""
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import BOT_TYPES


def kb(*rows):
    b = InlineKeyboardBuilder()
    for row in rows:
        b.row(*[InlineKeyboardButton(text=t, url=d) if d.startswith("http")
                else InlineKeyboardButton(text=t, callback_data=d) for t, d in row])
    return b.as_markup()


def maker_menu(is_admin: bool):
    rows = [[("➕ Bot yaratish", "mk:new")], [("🤖 Mening botlarim", "mk:my")],
            [("🎓 Talabalar va O'qituvchilar uchun", "edu:home")]]
    if is_admin:
        rows.append([("🛠 Admin panel", "adm:home")])
    return kb(*rows)


def types_kb():
    rows = [[(label, f"mk:type:{k}")] for k, label in BOT_TYPES.items()]
    rows.append([("⬅️ Orqaga", "mk:home")])
    return kb(*rows)


def join_kb(channels):
    rows = [[(f"📢 {c['title']}", c["link"])] for c in channels if c.get("link")]
    rows.append([("✅ Obunani tekshirish", "chk")])
    return kb(*rows)


def anon_menu():
    return kb([("🔍 Suhbatdosh topish", "an:find")], [("⏭ Keyingisi", "an:next"), ("⏹ Tugatish", "an:stop")])


def edu_home(bot_type: str):
    rows = [[("🎒 Talabalar uchun", "edu:st")], [("👨‍🏫 O'qituvchilar uchun", "edu:te")]]
    if bot_type == "maker":
        rows.append([("⬅️ Bosh menyu", "mk:home")])
    return kb(*rows)


def admin_home(bot_type: str):
    rows = [[("📊 Statistika", "adm:stats")],
            [("📢 Majburiy obuna", "adm:ch"), ("✉️ Xabar yuborish", "adm:bc")]]
    if bot_type == "maker":
        rows += [[("🤖 Botlarni boshqarish", "ma:bots")], [("💰 Reklama va Premium", "ma:ads")],
                 [("📚 Darsliklar bazasi", "cb:pdf"), ("🔑 AI API kalit", "cb:key")]]
    else:
        extra = {"kino": [("🎬 Kinolar bazasi", "cb:movie")], "ai": [("🔑 API kalit", "cb:key")],
                 "logo": [("🔑 API kalit", "cb:key")], "music": [("🔑 AudD kalit", "cb:key")],
                 "edu": [("🔑 API kalit", "cb:key"), ("📚 PDF baza", "cb:pdf")]}
        if bot_type in extra:
            rows.append(extra[bot_type])
        rows.append([("👋 Salomlashuv matni", "cb:welcome")])
    return kb(*rows)
