"""Telegram notification service for TenderScout UK."""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_telegram_config():
    """Get Telegram config from environment at runtime."""
    return (
        os.getenv("TELEGRAM_BOT_TOKEN", ""),
        os.getenv("TELEGRAM_CHAT_ID", ""),
    )


def format_budget(amount: Optional[float], currency: str = "GBP") -> str:
    """Format budget amount for display."""
    if not amount:
        return "Not specified"
    if amount >= 1_000_000:
        return f"£{amount / 1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"£{amount / 1_000:.0f}K"
    else:
        return f"£{amount:.0f}"


def format_tender_message(tender: dict) -> str:
    """Format a tender for Telegram notification."""
    score_emoji = "🔥" if tender.get("relevance_score", 0) >= 9 else "⭐" if tender.get("relevance_score", 0) >= 6 else "📋"

    msg = f"""{score_emoji} *New Tender Found*

*Title:* {tender.get('title', 'N/A')}
*Buyer:* {tender.get('buyer', 'N/A')}
*Budget:* {format_budget(tender.get('budget_amount'), tender.get('budget_currency', 'GBP'))}
*Deadline:* {tender.get('deadline', 'N/A')[:10] if tender.get('deadline') else 'Not specified'}
*Category:* {tender.get('category', 'N/A')}
*Source:* {tender.get('source', 'N/A')}
*Relevance Score:* {tender.get('relevance_score', 0)}/20

🔗 [View Tender]({tender.get('source_url', '#')})"""

    return msg


async def send_telegram_notification(tender: dict) -> bool:
    """Send a single tender notification via Telegram."""
    token, chat_id = get_telegram_config()
    if not token or not chat_id:
        logger.warning("Telegram credentials not configured. Skipping notification.")
        return False

    import httpx

    message = format_tender_message(tender)
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            })
            resp.raise_for_status()
            logger.info(f"Telegram notification sent for: {tender.get('title', '')[:50]}")
            return True
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False


async def send_batch_notifications(tenders: list[dict]) -> int:
    """Send notifications for multiple tenders. Returns count of successfully sent."""
    token, chat_id = get_telegram_config()
    if not token or not chat_id:
        logger.warning("Telegram credentials not configured.")
        return 0

    sent = 0
    for tender in tenders:
        success = await send_telegram_notification(tender)
        if success:
            sent += 1

    if sent > 0:
        logger.info(f"Sent {sent}/{len(tenders)} Telegram notifications")
    return sent
