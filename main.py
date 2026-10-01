"""Kirish nuqtasi: DB + aiohttp server (webhook/health) + barcha botlar + eslatma sikli."""
import asyncio
import os
import logging
import time
from datetime import datetime

from aiohttp import web

import config as cfg
from database import Database
from runtime import Manager
from utils import esc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s")
log = logging.getLogger("main")


async def reminder_loop(db, manager):
    """Har 30 soniyada vaqti kelgan eslatmalarni yuboradi."""
    while True:
        await asyncio.sleep(30)
        try:
            for r in await db.fetch("SELECT * FROM reminders WHERE done=0 AND due<=?", int(time.time())):
                await db.execute("UPDATE reminders SET done=1 WHERE id=?", r["id"])
                item = manager.by_scope.get(r["scope"])
                if item:
                    try:
                        await item.bot.send_message(r["user_id"], f"⏰ <b>Eslatma</b>\n{esc(r['text'])}")
                    except Exception:
                        pass
        except Exception:
            log.exception("reminder_loop")


async def main():
    if not cfg.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN o'rnatilmagan!")
    db = Database(cfg.DATABASE_URL)
    await db.connect()
    manager = Manager(db)

    app = web.Application()
    async def health(_):
        return web.Response(text="Maker bot is running")  # Render health check
    app.router.add_get("/", health)
    app.router.add_post("/wh/{key}", manager.webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", cfg.PORT).start()

    asyncio.create_task(reminder_loop(db, manager))
    await manager.start_all()
    if not db.pg:
        log.warning("SQLite ishlatilmoqda — Render'da ma'lumot yo'qoladi. DATABASE_URL (PostgreSQL) o'rnating!")
        if os.getenv("RENDER"):
            for a in cfg.ADMIN_IDS:
                try:
                    await manager.by_scope[0].bot.send_message(
                        a, "⚠️ <b>DATABASE_URL o'rnatilmagan.</b> Render'da SQLite har deploy/uyg'onishda o'chadi va "
                           "yaratilgan botlar yo'qoladi. PostgreSQL ulang. Holat: /diag")
                except Exception:
                    pass
    log.info("Rejim: %s", "WEBHOOK" if cfg.BASE_URL else "POLLING")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
