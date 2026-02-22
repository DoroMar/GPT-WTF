from __future__ import annotations

import json
import os
import time

from dotenv import load_dotenv
from datetime import datetime

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import Post
from .schemas import SettingsIn
from .services import (
    REDDIT_SOURCES,
    feed_cache,
    filter_posts_for_period,
    get_or_create_settings,
    parse_subreddit_flags,
    refresh_feed,
    send_to_telegram,
)

load_dotenv()

app = FastAPI(title="Cat Content Curator")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def apply_env_defaults():
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db)
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        channel = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
        min_ups = os.getenv("MIN_UPS")
        auto_refresh = os.getenv("AUTO_REFRESH", "false").lower() in {"1", "true", "yes", "on"}
        if token and not settings.telegram_bot_token:
            settings.telegram_bot_token = token
        if channel and not settings.telegram_channel_id:
            settings.telegram_channel_id = channel
        if min_ups and (settings.min_ups is None or settings.min_ups == 300):
            settings.min_ups = int(min_ups)
        settings.auto_refresh = settings.auto_refresh or auto_refresh
        db.commit()
    finally:
        db.close()


@app.get("/")
async def index(request: Request, period: str = "day", db: Session = Depends(get_db)):
    if time.time() > feed_cache.expires_at:
        await refresh_feed(db)

    settings = get_or_create_settings(db)
    flags = parse_subreddit_flags(settings)
    source_subs = sorted({x.split("_")[0] for x in REDDIT_SOURCES.keys()})

    items = filter_posts_for_period(feed_cache.items, period)
    for item in items:
        item["created_human"] = datetime.utcfromtimestamp(item["created_utc"]).strftime("%d.%m.%Y %H:%M UTC")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "posts": items,
            "period": period,
            "settings": settings,
            "subreddits": source_subs,
            "flags": flags,
        },
    )


@app.post("/settings")
async def update_settings(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    payload = SettingsIn(
        telegram_bot_token=form.get("telegram_bot_token", ""),
        telegram_channel_id=form.get("telegram_channel_id", ""),
        min_ups=int(form.get("min_ups", 300) or 0),
        auto_refresh=form.get("auto_refresh") == "on",
        subreddit_flags={k.replace("sub_", ""): True for k in form.keys() if k.startswith("sub_")},
    )

    settings = get_or_create_settings(db)
    settings.telegram_bot_token = payload.telegram_bot_token.strip()
    settings.telegram_channel_id = payload.telegram_channel_id.strip()
    settings.min_ups = payload.min_ups
    all_subs = {x.split("_")[0] for x in REDDIT_SOURCES.keys()}
    merged_flags = {sub: payload.subreddit_flags.get(sub, False) for sub in all_subs}
    settings.subreddit_flags = json.dumps(merged_flags, ensure_ascii=False)
    settings.auto_refresh = payload.auto_refresh
    db.commit()

    return JSONResponse({"ok": True, "message": "Настройки сохранены"})


@app.post("/refresh")
async def manual_refresh(db: Session = Depends(get_db)):
    await refresh_feed(db)
    return JSONResponse({"ok": True, "message": "Лента обновлена"})


@app.post("/send/{post_id}")
async def send_post(post_id: int, db: Session = Depends(get_db)):
    post = db.scalar(select(Post).where(Post.id == post_id))
    if not post:
        return JSONResponse({"ok": False, "message": "Пост не найден"}, status_code=404)

    settings = get_or_create_settings(db)
    ok, message = await send_to_telegram(settings.telegram_bot_token, settings.telegram_channel_id, post)
    return JSONResponse({"ok": ok, "message": message}, status_code=200 if ok else 400)


@app.get("/health")
def health():
    return {"status": "ok"}
