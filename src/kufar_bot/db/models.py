from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    groups: Mapped[list[SearchGroup]] = relationship(back_populates="user", cascade="all, delete-orphan")
    negative_phrases: Mapped[list[NegativePhrase]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    favorites: Mapped[list[Favorite]] = relationship(back_populates="user", cascade="all, delete-orphan")
    schedule: Mapped[Schedule | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class SearchGroup(Base):
    __tablename__ = "search_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    section_label: Mapped[str] = mapped_column(String(128), default="")
    region_label: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="groups")
    urls: Mapped[list[SearchUrl]] = relationship(back_populates="group", cascade="all, delete-orphan")
    negative_phrases: Mapped[list[NegativePhrase]] = relationship(back_populates="group")


class SearchUrl(Base):
    __tablename__ = "search_urls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("search_groups.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(Text)
    api_query: Mapped[str] = mapped_column(Text, default="{}")
    watermark_ad_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group: Mapped[SearchGroup] = relationship(back_populates="urls")


class NegativePhrase(Base):
    __tablename__ = "negative_phrases"
    __table_args__ = (UniqueConstraint("user_id", "phrase", "group_id", name="uq_user_phrase_group"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"))
    group_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("search_groups.id", ondelete="CASCADE"), nullable=True
    )
    phrase: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="negative_phrases")
    group: Mapped[SearchGroup | None] = relationship(back_populates="negative_phrases")


class Schedule(Base):
    __tablename__ = "schedules"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), primary_key=True)
    weekdays: Mapped[str] = mapped_column(String(32), default="0,1,2,3,4,5,6")
    run_times: Mapped[str] = mapped_column(String(256), default="08:00,14:00,20:00")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Minsk")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship(back_populates="schedule")


class PollRun(Base):
    __tablename__ = "poll_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SeenListing(Base):
    __tablename__ = "seen_listings"
    __table_args__ = (UniqueConstraint("user_id", "ad_id", "search_url_id", name="uq_seen_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"))
    ad_id: Mapped[int] = mapped_column(BigInteger)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("search_groups.id", ondelete="CASCADE"))
    search_url_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("search_urls.id", ondelete="CASCADE"), nullable=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "ad_id", name="uq_favorite"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"))
    ad_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(512), default="")
    url: Mapped[str] = mapped_column(Text, default="")
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="BYN")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="favorites")
