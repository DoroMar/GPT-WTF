from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from .database import Base


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("reddit_id", name="uq_posts_reddit_id"),)

    id = Column(Integer, primary_key=True)
    reddit_id = Column(String(32), nullable=False)
    title = Column(Text, nullable=False)
    title_ru = Column(Text, nullable=False)
    media_url = Column(Text, nullable=False)
    permalink = Column(Text, nullable=False)
    subreddit = Column(String(64), nullable=False)
    ups = Column(Integer, default=0)
    created_utc = Column(Integer, nullable=False)
    post_hint = Column(String(64), nullable=True)
    is_video = Column(Boolean, default=False)
    over_18 = Column(Boolean, default=False)
    media_type = Column(String(16), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)
    telegram_bot_token = Column(Text, default="")
    telegram_channel_id = Column(String(128), default="")
    min_ups = Column(Integer, default=300)
    subreddit_flags = Column(Text, default="{}")
    auto_refresh = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
