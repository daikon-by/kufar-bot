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


def _migrate_url_sections(connection: Connection) -> None:
    if not _has_column(connection, "search_urls", "section_label"):
        connection.execute(text("ALTER TABLE search_urls ADD COLUMN section_label VARCHAR(128) DEFAULT ''"))
    connection.execute(
        text(
            """
            UPDATE search_urls
            SET section_label = (
                SELECT COALESCE(section_label, '')
                FROM search_groups
                WHERE search_groups.id = search_urls.group_id
            )
            WHERE section_label IS NULL OR section_label = ''
            """
        )
    )


def _merge_duplicate_named_groups(connection: Connection) -> None:
    rows = connection.execute(
        text(
            """
            SELECT user_id, name, GROUP_CONCAT(id) AS ids
            FROM search_groups
            GROUP BY user_id, name
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    for row in rows:
        ids = sorted(int(part) for part in str(row.ids).split(",") if part)
        if len(ids) < 2:
            continue
        primary, *duplicates = ids
        for dup_id in duplicates:
            connection.execute(
                text(
                    """
                    DELETE FROM search_urls
                    WHERE group_id = :dup_id
                      AND url IN (
                          SELECT url FROM search_urls WHERE group_id = :primary
                      )
                    """
                ),
                {"primary": primary, "dup_id": dup_id},
            )
            connection.execute(
                text(
                    """
                    UPDATE search_urls
                    SET group_id = :primary,
                        section_label = CASE
                            WHEN section_label IS NULL OR section_label = '' THEN (
                                SELECT COALESCE(section_label, '')
                                FROM search_groups
                                WHERE id = :dup_id
                            )
                            ELSE section_label
                        END
                    WHERE group_id = :dup_id
                    """
                ),
                {"primary": primary, "dup_id": dup_id},
            )
            connection.execute(
                text(
                    """
                    DELETE FROM negative_phrases
                    WHERE group_id = :dup_id
                      AND phrase IN (
                          SELECT phrase FROM negative_phrases WHERE group_id = :primary
                      )
                    """
                ),
                {"primary": primary, "dup_id": dup_id},
            )
            connection.execute(
                text(
                    "UPDATE negative_phrases SET group_id = :primary WHERE group_id = :dup_id"
                ),
                {"primary": primary, "dup_id": dup_id},
            )
            connection.execute(
                text(
                    """
                    UPDATE seen_listings
                    SET group_id = :primary
                    WHERE group_id = :dup_id AND search_url_id IS NULL
                    """
                ),
                {"primary": primary, "dup_id": dup_id},
            )
            connection.execute(
                text("DELETE FROM search_groups WHERE id = :dup_id"),
                {"dup_id": dup_id},
            )
        connection.execute(
            text("UPDATE search_groups SET section_label = '' WHERE id = :primary"),
            {"primary": primary},
        )


def run_migrations(connection: Connection) -> None:
    Base.metadata.create_all(connection)

    if not _has_column(connection, "search_urls", "watermark_ad_id"):
        connection.execute(text("ALTER TABLE search_urls ADD COLUMN watermark_ad_id BIGINT"))
    if not _has_column(connection, "search_urls", "last_polled_at"):
        connection.execute(text("ALTER TABLE search_urls ADD COLUMN last_polled_at DATETIME"))

    _migrate_url_sections(connection)
    _merge_duplicate_named_groups(connection)

    if connection.dialect.name == "sqlite":
        _migrate_seen_listings(connection)
    elif not _has_column(connection, "seen_listings", "search_url_id"):
        connection.execute(
            text("ALTER TABLE seen_listings ADD COLUMN search_url_id INTEGER REFERENCES search_urls(id)")
        )
