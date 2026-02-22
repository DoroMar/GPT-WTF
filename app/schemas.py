from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsIn(BaseModel):
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""
    min_ups: int = Field(default=300, ge=0)
    auto_refresh: bool = False
    subreddit_flags: dict[str, bool] = {}


class TelegramSendIn(BaseModel):
    post_id: int
