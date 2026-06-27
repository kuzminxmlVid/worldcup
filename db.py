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

CREATE TABLE IF NOT EXISTS user_match_data (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    fixture_id BIGINT NOT NULL,
    prediction TEXT,
    note TEXT,
    post_match_thoughts TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id, fixture_id)
);

CREATE TABLE IF NOT EXISTS pending_inputs (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    fixture_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    source_message_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS match_card_messages (
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    fixture_id BIGINT NOT NULL,
    card_message_id BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chat_id, user_id, fixture_id)
);
"""


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)


async def init_db(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)
        await conn.execute("ALTER TABLE chats ADD COLUMN IF NOT EXISTS reminders_enabled BOOLEAN NOT NULL DEFAULT TRUE")
        await conn.execute("ALTER TABLE pending_inputs ADD COLUMN IF NOT EXISTS source_message_id BIGINT")
        await conn.execute("ALTER TABLE matches ADD COLUMN IF NOT EXISTS api_fixture_id BIGINT")
        await conn.execute("ALTER TABLE matches ADD COLUMN IF NOT EXISTS score_checked_at TIMESTAMPTZ")
        await conn.execute("ALTER TABLE user_match_data ADD COLUMN IF NOT EXISTS post_match_thoughts TEXT")


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
        await conn.execute("UPDATE chats SET is_active = FALSE WHERE chat_id = $1", chat_id)


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
        return await conn.fetchrow(
            "SELECT is_active, reminders_enabled FROM chats WHERE chat_id = $1",
            chat_id,
        )


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
        row = await conn.fetchrow("SELECT reminders_enabled FROM chats WHERE chat_id = $1", chat_id)
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
                    VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, NOW())
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



async def get_all_matches(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM matches
            ORDER BY kickoff_utc ASC
            """
        )


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


async def get_match_by_id(pool: asyncpg.Pool, fixture_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM matches WHERE fixture_id = $1", fixture_id)


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


async def get_user_match_data(pool: asyncpg.Pool, chat_id: int, user_id: int, fixture_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT prediction, note, post_match_thoughts, updated_at
            FROM user_match_data
            WHERE chat_id = $1
              AND user_id = $2
              AND fixture_id = $3
            """,
            chat_id,
            user_id,
            fixture_id,
        )


async def save_prediction(pool: asyncpg.Pool, chat_id: int, user_id: int, fixture_id: int, prediction: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_match_data(chat_id, user_id, fixture_id, prediction, updated_at)
            VALUES($1, $2, $3, $4, NOW())
            ON CONFLICT(chat_id, user_id, fixture_id) DO UPDATE SET
                prediction = EXCLUDED.prediction,
                updated_at = NOW()
            """,
            chat_id,
            user_id,
            fixture_id,
            prediction,
        )


async def save_note(pool: asyncpg.Pool, chat_id: int, user_id: int, fixture_id: int, note: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_match_data(chat_id, user_id, fixture_id, note, updated_at)
            VALUES($1, $2, $3, $4, NOW())
            ON CONFLICT(chat_id, user_id, fixture_id) DO UPDATE SET
                note = EXCLUDED.note,
                updated_at = NOW()
            """,
            chat_id,
            user_id,
            fixture_id,
            note,
        )



async def save_post_match_thoughts(pool: asyncpg.Pool, chat_id: int, user_id: int, fixture_id: int, thoughts: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_match_data(chat_id, user_id, fixture_id, post_match_thoughts, updated_at)
            VALUES($1, $2, $3, $4, NOW())
            ON CONFLICT(chat_id, user_id, fixture_id) DO UPDATE SET
                post_match_thoughts = EXCLUDED.post_match_thoughts,
                updated_at = NOW()
            """,
            chat_id,
            user_id,
            fixture_id,
            thoughts,
        )


async def clear_user_match_data(pool: asyncpg.Pool, chat_id: int, user_id: int, fixture_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM user_match_data
            WHERE chat_id = $1
              AND user_id = $2
              AND fixture_id = $3
            """,
            chat_id,
            user_id,
            fixture_id,
        )


async def set_pending_input(
    pool: asyncpg.Pool,
    chat_id: int,
    user_id: int,
    fixture_id: int,
    action: str,
    source_message_id: int | None = None,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO pending_inputs(chat_id, user_id, fixture_id, action, source_message_id, created_at)
            VALUES($1, $2, $3, $4, $5, NOW())
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                fixture_id = EXCLUDED.fixture_id,
                action = EXCLUDED.action,
                source_message_id = EXCLUDED.source_message_id,
                created_at = NOW()
            """,
            chat_id,
            user_id,
            fixture_id,
            action,
            source_message_id,
        )


async def get_pending_input(pool: asyncpg.Pool, chat_id: int, user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT fixture_id, action, source_message_id, created_at
            FROM pending_inputs
            WHERE chat_id = $1
              AND user_id = $2
            """,
            chat_id,
            user_id,
        )


async def clear_pending_input(pool: asyncpg.Pool, chat_id: int, user_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM pending_inputs
            WHERE chat_id = $1
              AND user_id = $2
            """,
            chat_id,
            user_id,
        )



async def search_matches_by_team(pool: asyncpg.Pool, query: str):
    pattern = f"%{query.strip()}%"
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM matches
            WHERE home_team ILIKE $1
               OR away_team ILIKE $1
            ORDER BY kickoff_utc ASC
            """,
            pattern,
        )


async def get_all_team_names(pool: asyncpg.Pool) -> list[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT team
            FROM (
                SELECT home_team AS team FROM matches
                UNION
                SELECT away_team AS team FROM matches
            ) teams
            ORDER BY team ASC
            """
        )
    return [r["team"] for r in rows]



async def update_match_score(
    pool: asyncpg.Pool,
    fixture_id: int,
    api_fixture_id: int | None,
    status_short: str | None,
    status_long: str | None,
    home_goals: int | None,
    away_goals: int | None,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE matches
            SET api_fixture_id = COALESCE($2, api_fixture_id),
                status_short = COALESCE($3, status_short),
                status_long = COALESCE($4, status_long),
                home_goals = $5,
                away_goals = $6,
                score_checked_at = NOW(),
                updated_at = NOW()
            WHERE fixture_id = $1
            """,
            fixture_id,
            api_fixture_id,
            status_short,
            status_long,
            home_goals,
            away_goals,
        )


async def save_match_card_message(
    pool: asyncpg.Pool,
    chat_id: int,
    user_id: int,
    fixture_id: int,
    card_message_id: int,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO match_card_messages(chat_id, user_id, fixture_id, card_message_id, updated_at)
            VALUES($1, $2, $3, $4, NOW())
            ON CONFLICT(chat_id, user_id, fixture_id) DO UPDATE SET
                card_message_id = EXCLUDED.card_message_id,
                updated_at = NOW()
            """,
            chat_id,
            user_id,
            fixture_id,
            card_message_id,
        )


async def get_match_card_message(
    pool: asyncpg.Pool,
    chat_id: int,
    user_id: int,
    fixture_id: int,
) -> int | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT card_message_id
            FROM match_card_messages
            WHERE chat_id = $1
              AND user_id = $2
              AND fixture_id = $3
            """,
            chat_id,
            user_id,
            fixture_id,
        )
    return int(row["card_message_id"]) if row else None



async def get_last_match_for_user(pool: asyncpg.Pool, chat_id: int, user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT m.*
            FROM match_card_messages c
            JOIN matches m ON m.fixture_id = c.fixture_id
            WHERE c.chat_id = $1
              AND c.user_id = $2
            ORDER BY c.updated_at DESC
            LIMIT 1
            """,
            chat_id,
            user_id,
        )


async def get_matches_for_score_update(pool: asyncpg.Pool, start_utc, end_utc):
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM matches
            WHERE kickoff_utc >= $1
              AND kickoff_utc < $2
              AND COALESCE(status_short, 'NS') NOT IN ('FT', 'AET', 'PEN')
            ORDER BY kickoff_utc ASC
            """,
            start_utc,
            end_utc,
        )



async def get_matches_for_score_backfill(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM matches
            WHERE kickoff_utc <= NOW()
              AND (
                    home_goals IS NULL
                 OR away_goals IS NULL
                 OR COALESCE(status_short, '') NOT IN ('FT', 'AET', 'PEN')
              )
            ORDER BY kickoff_utc ASC
            """
        )



async def get_group_standings(pool: asyncpg.Pool, group_name: str):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT home_team, away_team, home_goals, away_goals
            FROM matches
            WHERE group_name = $1
            ORDER BY kickoff_utc ASC
            """,
            group_name,
        )

    table: dict[str, dict] = {}

    def ensure_team(team: str) -> dict:
        if team not in table:
            table[team] = {
                "team": team,
                "played": 0,
                "points": 0,
                "gf": 0,
                "ga": 0,
                "gd": 0,
                "rank": 0,
            }
        return table[team]

    for row in rows:
        home = row["home_team"]
        away = row["away_team"]
        home_stats = ensure_team(home)
        away_stats = ensure_team(away)

        home_goals = row["home_goals"]
        away_goals = row["away_goals"]

        if home_goals is None or away_goals is None:
            continue

        home_stats["played"] += 1
        away_stats["played"] += 1
        home_stats["gf"] += int(home_goals)
        home_stats["ga"] += int(away_goals)
        away_stats["gf"] += int(away_goals)
        away_stats["ga"] += int(home_goals)

        if home_goals > away_goals:
            home_stats["points"] += 3
        elif home_goals < away_goals:
            away_stats["points"] += 3
        else:
            home_stats["points"] += 1
            away_stats["points"] += 1

    for stats in table.values():
        stats["gd"] = stats["gf"] - stats["ga"]

    ordered = sorted(
        table.values(),
        key=lambda x: (-x["points"], -x["gd"], -x["gf"], x["team"]),
    )

    for idx, stats in enumerate(ordered, start=1):
        stats["rank"] = idx

    return ordered



async def get_playoff_matches(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT *
            FROM matches
            WHERE
                (
                    round_name IS NOT NULL
                    AND (
                        round_name ILIKE '%финал%'
                        OR round_name ILIKE '%1/%'
                        OR round_name ILIKE '%round of%'
                        OR round_name ILIKE '%quarter%'
                        OR round_name ILIKE '%semi%'
                        OR round_name ILIKE '%third%'
                    )
                )
                OR kickoff_utc >= TIMESTAMPTZ '2026-06-28 00:00:00+00'
            ORDER BY kickoff_utc ASC
            """
        )



async def get_next_playoff_round_matches(pool: asyncpg.Pool):
    rows = await get_playoff_matches(pool)
    rows = list(rows or [])

    if not rows:
        return None, []

    def stage_key(row):
        name = str(row["round_name"] or "").lower()
        kickoff = row["kickoff_utc"]

        if "1/16" in name or "round of 32" in name:
            return 1, "1/16 финала"
        if "1/8" in name or "round of 16" in name:
            return 2, "1/8 финала"
        if "1/4" in name or "quarter" in name:
            return 3, "1/4 финала"
        if "1/2" in name or "semi" in name:
            return 4, "1/2 финала"
        if ("3" in name and "мест" in name) or "third" in name:
            return 6, "Матч за 3-е место"
        if "финал" in name or "final" in name:
            return 5, "Финал"

        # Date fallback for ESPN feeds with weak round names.
        if kickoff:
            day = kickoff.date()
            if day <= day.replace(year=2026, month=7, day=1):
                return 1, "1/16 финала"
            if day <= day.replace(year=2026, month=7, day=7):
                return 2, "1/8 финала"
            if day <= day.replace(year=2026, month=7, day=12):
                return 3, "1/4 финала"
            if day <= day.replace(year=2026, month=7, day=15):
                return 4, "1/2 финала"
            if day <= day.replace(year=2026, month=7, day=18):
                return 5, "Финал"

        return 99, row["round_name"] or "Плей-офф"

    def is_finished(row) -> bool:
        if row["home_goals"] is None or row["away_goals"] is None:
            return False
        return str(row["status_short"] or "").upper() in ("FT", "AET", "PEN", "FULL_TIME")

    grouped = {}
    labels = {}

    for row in rows:
        key, label = stage_key(row)
        grouped.setdefault(key, []).append(row)
        labels[key] = label

    for key in sorted(grouped.keys()):
        if key == 6:
            # Third-place match is not the "next round" until everything else is gone.
            continue

        round_rows = sorted(grouped[key], key=lambda r: r["kickoff_utc"])
        if any(not is_finished(row) for row in round_rows):
            return labels[key], round_rows

    # If all normal playoff rounds are finished, show third-place if it is still pending.
    if 6 in grouped:
        round_rows = sorted(grouped[6], key=lambda r: r["kickoff_utc"])
        if any(not is_finished(row) for row in round_rows):
            return labels[6], round_rows

    # Otherwise show the final completed round for historical access.
    last_key = max(grouped.keys())
    return labels[last_key], sorted(grouped[last_key], key=lambda r: r["kickoff_utc"])
