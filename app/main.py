"""TenderScout UK — Main FastAPI Application."""

import os
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from fastapi import FastAPI, Request, Query, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import init_db, get_tenders, get_tender_by_id, get_stats, get_unnotified_tenders, mark_as_notified, get_setting, set_setting
from app.crawler import run_all_crawlers
from app.notifications import send_batch_notifications, format_budget

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_crawl():
    """Scheduled task: crawl for new tenders and send notifications."""
    logger.info("Running scheduled crawl...")
    try:
        new_tenders = await run_all_crawlers(days_back=1)
        logger.info(f"Crawl complete. {len(new_tenders)} new tenders found.")

        # Send notifications for high-relevance tenders
        unnotified = await get_unnotified_tenders(min_score=6)
        if unnotified:
            sent = await send_batch_notifications(unnotified)
            if sent > 0:
                await mark_as_notified([t["id"] for t in unnotified[:sent]])
    except Exception as e:
        logger.error(f"Scheduled crawl error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifecycle: init DB and start scheduler."""
    await init_db()
    logger.info("Database initialized")

    # Initial crawl on startup (7 days back for first load)
    asyncio.create_task(initial_crawl())

    # Schedule recurring crawl every 60 minutes
    scheduler.add_job(scheduled_crawl, "interval", minutes=60, id="tender_crawl")
    scheduler.start()
    logger.info("Scheduler started (crawl every 60 min)")

    yield

    scheduler.shutdown()
    logger.info("Scheduler shut down")


async def initial_crawl():
    """Initial crawl with more history on startup."""
    await asyncio.sleep(2)  # Let the app start first
    logger.info("Running initial crawl (7 days back)...")
    try:
        await run_all_crawlers(days_back=7)
        logger.info("Initial crawl complete.")

        # Send notifications for high-relevance tenders
        unnotified = await get_unnotified_tenders(min_score=6)
        if unnotified:
            await send_batch_notifications(unnotified)
            await mark_as_notified([t["id"] for t in unnotified])
    except Exception as e:
        logger.error(f"Initial crawl error: {e}")


app = FastAPI(
    title="TenderScout UK",
    description="UK Government Tender Monitoring System",
    lifespan=lifespan,
)

import os
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Register template filters
templates.env.filters["format_budget"] = lambda amount, currency="GBP": format_budget(amount, currency)


def truncate_text(text: str, length: int = 150) -> str:
    """Truncate text to a given length."""
    if not text:
        return ""
    return text[:length] + "..." if len(text) > length else text

templates.env.filters["truncate_text"] = truncate_text


# ─── Web Routes ───────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    """Homepage with hero, stats, and recent tenders."""
    stats = await get_stats()
    recent_tenders, _ = await get_tenders(sort_by="published_at", per_page=6)
    top_tenders, _ = await get_tenders(sort_by="relevance_score", per_page=6, min_score=3)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "recent_tenders": recent_tenders,
        "top_tenders": top_tenders,
    })


@app.get("/tenders", response_class=HTMLResponse)
async def tenders_page(
    request: Request,
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    nhs_software: bool = Query(False),
    sort: str = Query("published_at"),
    order: str = Query("DESC"),
    page: int = Query(1, ge=1),
):
    """Tender listing page with search and filters."""
    tenders, total = await get_tenders(
        search=search,
        category=category,
        source=source,
        min_score=min_score,
        status=status,
        nhs_software=nhs_software,
        sort_by=sort,
        sort_order=order,
        page=page,
        per_page=20,
    )
    total_pages = max(1, (total + 19) // 20)

    categories = [
        "Technology", "Healthcare", "Construction", "Professional",
        "Engineering", "Education", "Transport", "Environment",
        "Security", "Research", "Facility", "Other"
    ]

    return templates.TemplateResponse("tenders.html", {
        "request": request,
        "tenders": tenders,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "search": search or "",
        "category": category or "",
        "source": source or "",
        "min_score": min_score,
        "status": status or "",
        "nhs_software": nhs_software,
        "sort": sort,
        "order": order,
        "categories": categories,
    })


@app.get("/tenders/{tender_id}", response_class=HTMLResponse)
async def tender_detail(request: Request, tender_id: int):
    """Tender detail page."""
    tender = await get_tender_by_id(tender_id)
    if not tender:
        return templates.TemplateResponse("404.html", {
            "request": request,
        }, status_code=404)

    return templates.TemplateResponse("tender_detail.html", {
        "request": request,
        "tender": tender,
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page to configure Telegram Bot and Chat ID."""
    bot_token = await get_setting("TELEGRAM_BOT_TOKEN")
    chat_id = await get_setting("TELEGRAM_CHAT_ID")
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "bot_token": bot_token or "",
        "chat_id": chat_id or "",
    })

@app.post("/settings", response_class=RedirectResponse)
async def update_settings(
    request: Request,
    bot_token: str = Form(""),
    chat_id: str = Form("")
):
    """Update settings."""
    if bot_token:
        await set_setting("TELEGRAM_BOT_TOKEN", bot_token)
    if chat_id:
        await set_setting("TELEGRAM_CHAT_ID", chat_id)
        
    # Redirect back to settings page
    return RedirectResponse(url="/settings", status_code=303)


# ─── API Routes ────────────────────────────────────────────────

@app.get("/api/tenders")
async def api_tenders(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """JSON API for tenders."""
    tenders, total = await get_tenders(
        search=search, category=category, source=source,
        min_score=min_score, page=page, per_page=per_page,
    )
    return JSONResponse({
        "tenders": tenders,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    })


@app.get("/api/stats")
async def api_stats():
    """JSON API for stats."""
    stats = await get_stats()
    return JSONResponse(stats)


@app.post("/api/crawl")
async def api_trigger_crawl(days_back: int = Query(3)):
    """Manually trigger a crawl."""
    new_tenders = await run_all_crawlers(days_back=days_back)
    return JSONResponse({
        "status": "ok",
        "new_tenders": len(new_tenders),
    })
