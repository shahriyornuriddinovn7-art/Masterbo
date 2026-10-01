"""Ma'lumotlar bazasi: SQLite (aiosqlite) yoki PostgreSQL (asyncpg) — bitta interfeys.
SQL'da `?` placeholder ishlatiladi, PostgreSQL uchun avtomatik $1,$2.. ga o'giriladi.
scope: 0 = Maker bot, >0 = yaratilgan bot ID (multitenancy)."""
import os
import re
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS bots(id {PK}, owner_id BIGINT NOT NULL, token TEXT NOT NULL UNIQUE, username TEXT,
  bot_id BIGINT, type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at BIGINT);
CREATE TABLE IF NOT EXISTS users(scope BIGINT, user_id BIGINT, name TEXT, joined BIGINT, blocked INTEGER DEFAULT 0,
  PRIMARY KEY(scope, user_id));
CREATE TABLE IF NOT EXISTS channels(id {PK}, scope BIGINT, ref TEXT, title TEXT, link TEXT);
CREATE TABLE IF NOT EXISTS settings(scope BIGINT, key TEXT, value TEXT, PRIMARY KEY(scope, key));
CREATE TABLE IF NOT EXISTS premium(user_id BIGINT PRIMARY KEY, until BIGINT);
CREATE TABLE IF NOT EXISTS movies(scope BIGINT, code TEXT, file_id TEXT, ftype TEXT, title TEXT, PRIMARY KEY(scope, code));
CREATE TABLE IF NOT EXISTS materials(id {PK}, scope BIGINT, title TEXT, file_id TEXT);
CREATE TABLE IF NOT EXISTS reminders(id {PK}, scope BIGINT, user_id BIGINT, text TEXT, due BIGINT, done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS schedule(id {PK}, scope BIGINT, user_id BIGINT, day TEXT, line TEXT);
CREATE TABLE IF NOT EXISTS students(id {PK}, scope BIGINT, teacher_id BIGINT, name TEXT);
CREATE TABLE IF NOT EXISTS attendance(id {PK}, student_id BIGINT, day TEXT, present INTEGER);
"""


class Database:
    def __init__(self, url: str):
        self.url = url
        self.pg = url.startswith(("postgres://", "postgresql://"))
        self.pool = None
        self.conn = None

    async def connect(self):
        if self.pg:
            import asyncpg
            self.pool = await asyncpg.create_pool(self.url.replace("postgres://", "postgresql://", 1),
                                                  min_size=1, max_size=10)
        else:
            import aiosqlite
            path = self.url.replace("sqlite:///", "")
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self.conn = await aiosqlite.connect(path)
            self.conn.row_factory = aiosqlite.Row
            await self.conn.execute("PRAGMA journal_mode=WAL")
        pk = "BIGSERIAL PRIMARY KEY" if self.pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        for stmt in SCHEMA.replace("{PK}", pk).split(";"):
            if stmt.strip():
                await self.execute(stmt)

    def _q(self, sql: str) -> str:
        if not self.pg:
            return sql
        n = 0

        def rep(_):
            nonlocal n
            n += 1
            return f"${n}"
        return re.sub(r"\?", rep, sql)

    async def execute(self, sql, *a):
        if self.pg:
            async with self.pool.acquire() as c:
                await c.execute(self._q(sql), *a)
        else:
            await self.conn.execute(sql, a)
            await self.conn.commit()

    async def fetch(self, sql, *a) -> list[dict]:
        if self.pg:
            async with self.pool.acquire() as c:
                return [dict(r) for r in await c.fetch(self._q(sql), *a)]
        cur = await self.conn.execute(sql, a)
        return [dict(r) for r in await cur.fetchall()]

    async def fetchrow(self, sql, *a):
        rows = await self.fetch(sql, *a)
        return rows[0] if rows else None

    async def fetchval(self, sql, *a):
        if self.pg:
            async with self.pool.acquire() as c:
                return await c.fetchval(self._q(sql), *a)
        cur = await self.conn.execute(sql, a)
        row = await cur.fetchone()
        await self.conn.commit()  # INSERT ... RETURNING uchun
        return row[0] if row else None

    # ---- yordamchi metodlar ----
    async def get_setting(self, scope, key, default=None):
        v = await self.fetchval("SELECT value FROM settings WHERE scope=? AND key=?", scope, key)
        return v if v is not None else default

    async def set_setting(self, scope, key, value):
        await self.execute("INSERT INTO settings(scope,key,value) VALUES(?,?,?) "
                           "ON CONFLICT(scope,key) DO UPDATE SET value=excluded.value", scope, key, str(value))

    async def del_setting(self, scope, key):
        await self.execute("DELETE FROM settings WHERE scope=? AND key=?", scope, key)

    async def add_user(self, scope, uid, name):
        await self.execute("INSERT INTO users(scope,user_id,name,joined,blocked) VALUES(?,?,?,?,0) "
                           "ON CONFLICT(scope,user_id) DO UPDATE SET name=excluded.name, blocked=0",
                           scope, uid, name, int(time.time()))

    async def is_premium(self, uid) -> bool:
        v = await self.fetchval("SELECT until FROM premium WHERE user_id=?", uid)
        return bool(v and v > time.time())

    async def purge_scope(self, scope):
        await self.execute("DELETE FROM attendance WHERE student_id IN (SELECT id FROM students WHERE scope=?)", scope)
        for t in ("users", "channels", "settings", "movies", "materials", "reminders", "schedule", "students"):
            await self.execute(f"DELETE FROM {t} WHERE scope=?", scope)
