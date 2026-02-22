from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from deep_translator import GoogleTranslator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import AppSetting, Post

REDDIT_SOURCES = {
    "cats_day": "https://www.reddit.com/r/cats/top.json?t=day&limit=50",
    "cats_week": "https://www.reddit.com/r/cats/top.json?t=week&limit=50",
    "aww_day": "https://www.reddit.com/r/aww/top.json?t=day&limit=50",
    "catvideos_day": "https://www.reddit.com/r/CatVideos/top.json?t=day&limit=50",
    "funnycats_week": "https://www.reddit.com/r/funnycats/top.json?t=week&limit=50",
}

ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".mp4")


class FeedCache:
    def __init__(self) -> None:
        self.expires_at = 0.0
        self.items: list[dict[str, Any]] = []


feed_cache = FeedCache()


def get_or_create_settings(db: Session) -> AppSetting:
    settings = db.scalar(select(AppSetting).limit(1))
    if settings:
        return settings
    settings = AppSetting()
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def parse_subreddit_flags(settings: AppSetting) -> dict[str, bool]:
    try:
        data = json.loads(settings.subreddit_flags or "{}")
        if isinstance(data, dict):
            return {k: bool(v) for k, v in data.items()}
    except json.JSONDecodeError:
        pass
    return {}


def build_media_info(post_data: dict[str, Any]) -> tuple[str | None, str | None]:
    url = post_data.get("url") or ""
    is_video = bool(post_data.get("is_video"))

    if is_video:
        reddit_video = (((post_data.get("media") or {}).get("reddit_video") or {}).get("fallback_url"))
        if reddit_video:
            return reddit_video, "video"
        if "v.redd.it" in url:
            return url, "video"

    lowered = url.lower()
    if any(lowered.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        media_type = "video" if lowered.endswith(".mp4") else "image"
        return url, media_type

    hint = (post_data.get("post_hint") or "").lower()
    if hint in {"image", "hosted:video", "rich:video"}:
        if "reddit_video" in (post_data.get("secure_media") or {}):
            fallback = (((post_data.get("secure_media") or {}).get("reddit_video") or {}).get("fallback_url"))
            if fallback:
                return fallback, "video"
        if hint == "image":
            return url, "image"

    return None, None


def translate_to_russian(text: str) -> str:
    if not text.strip():
        return text
    try:
        return GoogleTranslator(source="auto", target="ru").translate(text)
    except Exception:
        return text


def extract_posts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    children = (((payload.get("data") or {}).get("children")) or [])
    rows: list[dict[str, Any]] = []
    for child in children:
        data = child.get("data") or {}
        if data.get("over_18"):
            continue
        media_url, media_type = build_media_info(data)
        if not media_url:
            continue

        rows.append(
            {
                "reddit_id": data.get("id", ""),
                "title": data.get("title", "Без названия"),
                "media_url": media_url,
                "permalink": f"https://www.reddit.com{data.get('permalink', '')}",
                "ups": int(data.get("ups") or 0),
                "created_utc": int(data.get("created_utc") or 0),
                "subreddit": data.get("subreddit", "unknown"),
                "post_hint": data.get("post_hint") or "",
                "is_video": bool(data.get("is_video")),
                "over_18": bool(data.get("over_18")),
                "media_type": media_type,
            }
        )
    return rows


async def fetch_json_with_retry(client: httpx.AsyncClient, url: str, retries: int = 3) -> dict[str, Any]:
    delay = 1
    for attempt in range(retries):
        try:
            resp = await client.get(url)
            if resp.status_code == 429:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception:
            if attempt == retries - 1:
                return {}
            await asyncio.sleep(delay)
            delay *= 2
    return {}


def viral_score(post: Post, now_ts: int) -> float:
    age_hours = max(1.0, (now_ts - post.created_utc) / 3600)
    freshness = 1 / age_hours
    video_bonus = 1.35 if post.media_type == "video" else 1.0
    return (post.ups * 0.85 + freshness * 150) * video_bonus


async def refresh_feed(db: Session) -> list[Post]:
    settings = get_or_create_settings(db)
    subreddit_flags = parse_subreddit_flags(settings)

    headers = {"User-Agent": "cat-content-curator/1.0"}
    all_rows: list[dict[str, Any]] = []
    async with httpx.AsyncClient(headers=headers, timeout=20.0, follow_redirects=True) as client:
        for source_key, url in REDDIT_SOURCES.items():
            subreddit_name = source_key.split("_")[0]
            if subreddit_name in subreddit_flags and not subreddit_flags[subreddit_name]:
                continue
            payload = await fetch_json_with_retry(client, url)
            all_rows.extend(extract_posts(payload))

    dedup: dict[str, dict[str, Any]] = {}
    for row in all_rows:
        if not row["reddit_id"]:
            continue
        prev = dedup.get(row["reddit_id"])
        if not prev or row["ups"] > prev["ups"]:
            dedup[row["reddit_id"]] = row

    for row in dedup.values():
        row["title_ru"] = translate_to_russian(row["title"])
        if row["ups"] < settings.min_ups:
            continue
        post = Post(**row)
        db.add(post)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()

    now_ts = int(datetime.now(timezone.utc).timestamp())
    posts = db.scalars(select(Post)).all()
    posts.sort(key=lambda p: viral_score(p, now_ts), reverse=True)
    selected = posts[:100]

    feed_cache.items = [serialize_post(p) for p in selected]
    feed_cache.expires_at = time.time() + 1800
    return selected


def serialize_post(post: Post) -> dict[str, Any]:
    return {
        "id": post.id,
        "title": post.title,
        "title_ru": post.title_ru,
        "media_url": post.media_url,
        "permalink": post.permalink,
        "ups": post.ups,
        "created_utc": post.created_utc,
        "subreddit": post.subreddit,
        "media_type": post.media_type,
        "is_video": post.is_video,
    }


def filter_posts_for_period(items: list[dict[str, Any]], period: str) -> list[dict[str, Any]]:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    period_sec = 86400 if period == "day" else 7 * 86400
    scoped = [p for p in items if now_ts - p["created_utc"] <= period_sec]
    scoped.sort(
        key=lambda p: (p["ups"] * 0.85 + (150 / max(1, (now_ts - p["created_utc"]) / 3600))) * (1.35 if p["media_type"] == "video" else 1.0),
        reverse=True,
    )
    return scoped


async def send_to_telegram(token: str, channel_id: str, post: Post) -> tuple[bool, str]:
    if not token or not channel_id:
        return False, "Укажите Bot Token и Channel ID в настройках"

    caption = f"{post.title_ru}\n\nИсточник: {post.permalink}"
    endpoint = "sendVideo" if post.media_type == "video" else "sendPhoto"
    payload = {
        "chat_id": channel_id,
        "caption": caption[:1024],
        "parse_mode": "HTML",
    }
    key = "video" if post.media_type == "video" else "photo"
    payload[key] = post.media_url

    url = f"https://api.telegram.org/bot{token}/{endpoint}"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(url, json=payload)
            if resp.is_success and (resp.json().get("ok") is True):
                return True, "Отправлено в Telegram"
            return False, f"Ошибка Telegram: {resp.text[:180]}"
        except Exception as exc:
            return False, f"Сбой отправки: {exc}"
