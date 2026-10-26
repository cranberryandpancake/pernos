import aiosqlite, time

DB = "verify.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS pending (
    discord_id  INTEGER PRIMARY KEY,
    code        TEXT    NOT NULL,
    issued_at   INTEGER NOT NULL,
    expires_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS verified (
    origin_id   TEXT    PRIMARY KEY,
    discord_id  INTEGER NOT NULL,
    char_name   TEXT    NOT NULL,
    server_id   TEXT    NOT NULL,
    verified_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_discord ON verified(discord_id);
"""


async def init():
    async with aiosqlite.connect(DB) as c:
        await c.executescript(SCHEMA)
        await c.commit()


async def issue_code(discord_id: int, code: str, ttl: int = 600) -> int:
    now = int(time.time())
    async with aiosqlite.connect(DB) as c:
        await c.execute("INSERT OR REPLACE INTO pending VALUES (?,?,?,?)",
                        (discord_id, code, now, now + ttl))
        await c.commit()
    return now


async def get_pending(discord_id: int):
    async with aiosqlite.connect(DB) as c:
        cur = await c.execute(
            "SELECT code, issued_at, expires_at FROM pending WHERE discord_id=?",
            (discord_id,))
        return await cur.fetchone()


async def find_owner(origin_id: str):
    async with aiosqlite.connect(DB) as c:
        cur = await c.execute(
            "SELECT discord_id FROM verified WHERE origin_id=?", (origin_id,))
        row = await cur.fetchone()
        return row[0] if row else None


async def save_verified(origin_id, discord_id, name, server_id):
    async with aiosqlite.connect(DB) as c:
        await c.execute("INSERT OR REPLACE INTO verified VALUES (?,?,?,?,?)",
                        (origin_id, discord_id, name, server_id, int(time.time())))
        await c.execute("DELETE FROM pending WHERE discord_id=?", (discord_id,))
        await c.commit()