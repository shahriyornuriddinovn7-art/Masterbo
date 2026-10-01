"""Multitenancy yadrosi: Maker bot va barcha child botlarni bitta jarayonda ishga tushiradi.
Webhook rejimi (BASE_URL bor): har bir bot uchun /wh/{key}; yo'q bo'lsa — polling."""
import asyncio
import hashlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from aiohttp import web

import config as cfg
from handlers.ai_chat import build_ai_router
from handlers.anon import build_anon_router
from handlers.child_admin import build_child_admin
from handlers.common import build_common_router
from handlers.downloader import build_dl_router
from handlers.edu import build_edu_router
from handlers.kino import build_kino_router
from handlers.logo import build_logo_router
from handlers.maker import build_maker_router
from handlers.maker_admin import build_maker_admin
from handlers.music import build_music_router
from handlers.shared_admin import build_shared_admin
from utils import SubscriptionMiddleware, spawn

log = logging.getLogger("runtime")

TYPE_ROUTERS = {"kino": build_kino_router, "music": build_music_router, "ai": build_ai_router,
                "logo": build_logo_router, "edu": build_edu_router, "dl": build_dl_router, "anon": build_anon_router}


class Item:
    def __init__(self, key, bot, dp, scope):
        self.key, self.bot, self.dp, self.scope, self.task = key, bot, dp, scope, None


class Manager:
    def __init__(self, db):
        self.db = db
        self.items: dict[str, Item] = {}
        self.by_scope: dict[int, Item] = {}
        self.sub_mw = SubscriptionMiddleware(db)
        self.lock = asyncio.Lock()
        self.errors: dict[int, str] = {}

    def _dispatcher(self, scope, bot_type, admin_ids) -> Dispatcher:
        # Har bir bot uchun alohida Dispatcher + yangi Router nusxalari (router ikki joyga ulanmaydi)
        dp = Dispatcher(storage=MemoryStorage(), db=self.db, manager=self, scope=scope,
                        bot_type=bot_type, admin_ids=admin_ids)
        dp.message.outer_middleware(self.sub_mw)
        dp.callback_query.outer_middleware(self.sub_mw)
        dp.include_router(build_common_router())      # /start, /cancel, chk — birinchi
        dp.include_router(build_shared_admin())       # /admin, statistika, obuna, broadcast
        dp.include_router(build_child_admin())        # kontent / API kalit
        if bot_type == "maker":
            dp.include_router(build_maker_admin())
            dp.include_router(build_maker_router())
            dp.include_router(build_edu_router())     # Maker botda ham Talaba/O'qituvchi bo'limi
        else:
            dp.include_router(TYPE_ROUTERS[bot_type]())
        return dp

    @staticmethod
    def _key(token):
        return hashlib.sha256((token + cfg.WEBHOOK_SECRET).encode()).hexdigest()[:24]

    async def _launch(self, scope, token, bot_type, admin_ids):
        async with self.lock:
            cur = self.by_scope.get(scope)
            if cur and cur.bot.token == token:
                return  # allaqachon ishlayapti (masalan, webhook orqali yuklangan)
            await self.stop(scope)
            await self._launch_locked(scope, token, bot_type, admin_ids)

    async def _launch_locked(self, scope, token, bot_type, admin_ids):
        bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        try:
            await bot.get_me()
        except Exception:
            await bot.session.close()
            raise
        dp = self._dispatcher(scope, bot_type, admin_ids)
        item = Item(self._key(token), bot, dp, scope)
        types = dp.resolve_used_update_types()
        if cfg.BASE_URL:
            await bot.set_webhook(f"{cfg.BASE_URL.rstrip('/')}/wh/{item.key}", secret_token=cfg.WEBHOOK_SECRET,
                                  allowed_updates=types, max_connections=40)
        else:
            await bot.delete_webhook()
            item.task = asyncio.create_task(dp.start_polling(bot, allowed_updates=types, handle_signals=False))
        self.items[item.key] = item
        self.by_scope[scope] = item

    async def start_child(self, row) -> bool:
        try:
            await self._launch(row["id"], row["token"], row["type"], [row["owner_id"]])
            return True
        except TelegramUnauthorizedError:
            await self.db.execute("UPDATE bots SET status='invalid' WHERE id=?", row["id"])
        except Exception as e:
            log.exception("Bot #%s ishga tushmadi", row["id"])
            self.errors[row["id"]] = f"{type(e).__name__}: {e}"
        return False

    async def stop(self, scope):
        item = self.by_scope.pop(scope, None)
        if not item:
            return
        self.items.pop(item.key, None)
        if item.task:
            item.task.cancel()
        else:
            try:
                await item.bot.delete_webhook()
            except TelegramAPIError:
                pass
        await item.bot.session.close()

    async def remove(self, bot_id):
        await self.stop(bot_id)
        await self.db.purge_scope(bot_id)
        await self.db.execute("DELETE FROM bots WHERE id=?", bot_id)

    async def start_all(self):
        await self._launch(0, cfg.BOT_TOKEN, "maker", cfg.ADMIN_IDS)
        log.info("Maker bot ishga tushdi")
        for row in await self.db.fetch("SELECT * FROM bots WHERE status='active'"):
            await self.start_child(row)
            await asyncio.sleep(0.2)  # set_webhook limitlariga tushmaslik uchun
        log.info("Child botlar: %d", len(self.by_scope) - 1)

    async def _lazy(self, key):
        """Sovuq start: bot hali yuklanmagan bo'lsa, update kelganda uni bazadan yuklaymiz."""
        if key == self._key(cfg.BOT_TOKEN):
            await self._launch(0, cfg.BOT_TOKEN, "maker", cfg.ADMIN_IDS)
        else:
            for row in await self.db.fetch("SELECT * FROM bots WHERE status='active'"):
                if self._key(row["token"]) == key:
                    await self.start_child(row)
                    break
        return self.items.get(key)

    async def webhook(self, request: web.Request):
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != cfg.WEBHOOK_SECRET:
            return web.Response(status=403)
        key = request.match_info["key"]
        item = self.items.get(key) or await self._lazy(key)
        if not item:
            return web.Response(text="ok")  # noma'lum/o'chirilgan bot: Telegram qayta urinmasin
        update = Update.model_validate(await request.json(), context={"bot": item.bot})
        spawn(item.dp.feed_update(item.bot, update))  # Telegram'ga tez javob qaytaramiz
        return web.Response(text="ok")
