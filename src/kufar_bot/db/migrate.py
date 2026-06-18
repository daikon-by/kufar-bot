from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from kufar_bot.db.models import Base


def _has_column(connection: Connection, table: str, column: str) -> bool:
    return column in {col["name"] for col in inspect(connection).get_columns(table)}


def _migrate_seen_listings(connection: Connection) -> None:
    if _has_column(connection, "seen_listings", "search_url_id"):
        return

    connection.execute(
        text(
            """
            CREATE TABLE seen_listings_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT NOT NULL,
                ad_id BIGINT NOT NULL,
                group_id INTEGER NOT NULL,
                search_url_id INTEGER REFERENCES search_urls(id) ON DELETE CASCADE,
                first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                notified_at DATETIME,
                UNIQUE (user_id, ad_id, search_url_id)
            )
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO seen_listings_new (id, user_id, ad_id, group_id, search_url_id, first_seen_at, notified_at)
            SELECT id, user_id, ad_id, group_id, NULL, first_seen_at, notified_at
            FROM seen_listings
            """
        )
    )
    connection.execute(text("DROP TABLE seen_listings"))
    connection.execute(text("ALTER TABLE seen_listings_new RENAME TO seen_listings"))


def run_migrations(connection: Connection) -> None:
    Base.metadata.create_all(connection)

    if not _has_column(connection, "search_urls", "watermark_ad_id"):
        connection.execute(text("ALTER TABLE search_urls ADD COLUMN watermark_ad_id BIGINT"))
    if not _has_column(connection, "search_urls", "last_polled_at"):
        connection.execute(text("ALTER TABLE search_urls ADD COLUMN last_polled_at DATETIME"))

    if connection.dialect.name == "sqlite":
        _migrate_seen_listings(connection)
    elif not _has_column(connection, "seen_listings", "search_url_id"):
        connection.execute(
            text("ALTER TABLE seen_listings ADD COLUMN search_url_id INTEGER REFERENCES search_urls(id)")
        )
