import asyncpg


CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id BIGINT PRIMARY KEY,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    reminders_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS matches (
    fixture_id BIGINT PRIMARY KEY,
    kickoff_utc TIMESTAMPTZ NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    group_name TEXT,
    round_name TEXT,
    venue TEXT,
    status_short TEXT,
    status_long TEXT,
    home_goals INTEGER,
    away_goals INTEGER,
    raw JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sent_reminders (
    fixture_id BIGINT NOT NULL REFERENCES matches(fixture_id) ON DELETE CASCADE,
    chat_id BIGINT NOT NULL REFERENCES chats(chat_id) ON DELETE CASCADE,
    reminder_type TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (fixture_id, chat_id, reminder_type)
);
"""


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)


async def init_db(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)
        await conn.execute("ALTER TABLE chats ADD COLUMN IF NOT EXISTS reminders_enabled BOOLEAN NOT NULL DEFAULT TRUE")


async def add_chat(pool: asyncpg.Pool, chat_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO chats(chat_id, is_active, reminders_enabled)
            VALUES($1, TRUE, TRUE)
            ON CONFLICT(chat_id) DO UPDATE SET is_active = TRUE
            """,
            chat_id,
        )


async def stop_chat(pool: asyncpg.Pool, chat_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE chats SET is_active = FALSE WHERE chat_id = $1",
            chat_id,
        )


async def get_active_chats(pool: asyncpg.Pool) -> list[int]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT chat_id FROM chats WHERE is_active = TRUE")
    return [r["chat_id"] for r in rows]


async def get_active_reminder_chats(pool: asyncpg.Pool) -> list[int]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT chat_id FROM chats WHERE is_active = TRUE AND reminders_enabled = TRUE"
        )
    return [r["chat_id"] for r in rows]


async def get_chat_settings(pool: asyncpg.Pool, chat_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT is_active, reminders_enabled FROM chats WHERE chat_id = $1",
            chat_id,
        )
    return row


async def set_reminders_enabled(pool: asyncpg.Pool, chat_id: int, enabled: bool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO chats(chat_id, is_active, reminders_enabled)
            VALUES($1, TRUE, $2)
            ON CONFLICT(chat_id) DO UPDATE SET is_active = TRUE, reminders_enabled = $2
            """,
            chat_id,
            enabled,
        )


async def toggle_reminders(pool: asyncpg.Pool, chat_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT reminders_enabled FROM chats WHERE chat_id = $1",
            chat_id,
        )
        if row is None:
            await conn.execute(
                "INSERT INTO chats(chat_id, is_active, reminders_enabled) VALUES($1, TRUE, FALSE)",
                chat_id,
            )
            return False

        new_value = not bool(row["reminders_enabled"])
        await conn.execute(
            "UPDATE chats SET reminders_enabled = $2, is_active = TRUE WHERE chat_id = $1",
            chat_id,
            new_value,
        )
        return new_value


async def replace_matches(pool: asyncpg.Pool, matches: list[dict]) -> int:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM matches")
            for match in matches:
                await conn.execute(
                    """
                    INSERT INTO matches(
                        fixture_id,
                        kickoff_utc,
                        home_team,
                        away_team,
                        group_name,
                        round_name,
                        venue,
                        status_short,
                        status_long,
                        home_goals,
                        away_goals,
                        raw,
                        updated_at
                    )
                    VALUES(
                        $1, $2, $3, $4, $5, $6, $7,
                        $8, $9, $10, $11, $12::jsonb, NOW()
                    )
                    """,
                    match["fixture_id"],
                    match["kickoff_utc"],
                    match["home_team"],
                    match["away_team"],
                    match.get("group_name"),
                    match.get("round_name"),
                    match.get("venue"),
                    match.get("status_short"),
                    match.get("status_long"),
                    match.get("home_goals"),
                    match.get("away_goals"),
                    match["raw"],
                )
    return len(matches)


async def get_matches_between(pool: asyncpg.Pool, start_utc, end_utc):
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM matches
            WHERE kickoff_utc >= $1
              AND kickoff_utc < $2
            ORDER BY kickoff_utc ASC
            """,
            start_utc,
            end_utc,
        )


async def get_upcoming_for_reminder(pool: asyncpg.Pool, start_utc, end_utc):
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM matches
            WHERE kickoff_utc >= $1
              AND kickoff_utc < $2
              AND COALESCE(status_short, 'NS') IN ('NS', 'TBD', 'SCHEDULED')
            ORDER BY kickoff_utc ASC
            """,
            start_utc,
            end_utc,
        )


async def was_reminder_sent(pool: asyncpg.Pool, fixture_id: int, chat_id: int, reminder_type: str) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 1
            FROM sent_reminders
            WHERE fixture_id = $1
              AND chat_id = $2
              AND reminder_type = $3
            """,
            fixture_id,
            chat_id,
            reminder_type,
        )
    return row is not None


async def mark_reminder_sent(pool: asyncpg.Pool, fixture_id: int, chat_id: int, reminder_type: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sent_reminders(fixture_id, chat_id, reminder_type)
            VALUES($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            fixture_id,
            chat_id,
            reminder_type,
        )


async def get_debug_stats(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM matches")
        first_row = await conn.fetchrow("SELECT * FROM matches ORDER BY kickoff_utc ASC LIMIT 1")
        last_row = await conn.fetchrow("SELECT * FROM matches ORDER BY kickoff_utc DESC LIMIT 1")
        next_rows = await conn.fetch(
            """
            SELECT *
            FROM matches
            WHERE kickoff_utc >= NOW()
            ORDER BY kickoff_utc ASC
            LIMIT 8
            """
        )
    return count, first_row, last_row, next_rows


async def get_next_match(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT *
            FROM matches
            WHERE kickoff_utc >= NOW()
            ORDER BY kickoff_utc ASC
            LIMIT 1
            """
        )
