"""Database setup and operations for TenderScout UK."""

import aiosqlite
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tenders.db")


async def get_db():
    """Get database connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """Initialize the database schema."""
    db = await get_db()
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tenders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ocid TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                buyer TEXT,
                budget_amount REAL,
                budget_currency TEXT DEFAULT 'GBP',
                deadline TEXT,
                source TEXT,
                source_url TEXT,
                published_at TEXT,
                relevance_score INTEGER DEFAULT 0,
                status TEXT DEFAULT 'open',
                category TEXT,
                cpv_code TEXT,
                cpv_description TEXT,
                location TEXT,
                procurement_method TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notified INTEGER DEFAULT 0,
                is_sme_friendly INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenders_relevance
            ON tenders(relevance_score DESC)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenders_published
            ON tenders(published_at DESC)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenders_category
            ON tenders(category)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    finally:
        await db.close()


async def upsert_tender(tender: dict) -> bool:
    """Insert or update a tender. Returns True if it's a new tender."""
    db = await get_db()
    try:
        # Check if exists
        cursor = await db.execute(
            "SELECT id FROM tenders WHERE ocid = ?", (tender["ocid"],)
        )
        existing = await cursor.fetchone()

        if existing:
            await db.execute("""
                UPDATE tenders SET
                    title = ?, description = ?, buyer = ?,
                    budget_amount = ?, budget_currency = ?,
                    deadline = ?, source = ?, source_url = ?,
                    published_at = ?, relevance_score = ?,
                    status = ?, category = ?, cpv_code = ?,
                    cpv_description = ?, location = ?,
                    procurement_method = ?, is_sme_friendly = ?
                WHERE ocid = ?
            """, (
                tender.get("title"), tender.get("description"),
                tender.get("buyer"), tender.get("budget_amount"),
                tender.get("budget_currency", "GBP"),
                tender.get("deadline"), tender.get("source"),
                tender.get("source_url"), tender.get("published_at"),
                tender.get("relevance_score", 0), tender.get("status", "open"),
                tender.get("category"), tender.get("cpv_code"),
                tender.get("cpv_description"), tender.get("location"),
                tender.get("procurement_method"), tender.get("is_sme_friendly", 0), tender["ocid"]
            ))
            await db.commit()
            return False
        else:
            await db.execute("""
                INSERT INTO tenders (
                    ocid, title, description, buyer,
                    budget_amount, budget_currency, deadline,
                    source, source_url, published_at,
                    relevance_score, status, category,
                    cpv_code, cpv_description, location,
                    procurement_method, is_sme_friendly
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tender["ocid"], tender.get("title"),
                tender.get("description"), tender.get("buyer"),
                tender.get("budget_amount"),
                tender.get("budget_currency", "GBP"),
                tender.get("deadline"), tender.get("source"),
                tender.get("source_url"), tender.get("published_at"),
                tender.get("relevance_score", 0),
                tender.get("status", "open"), tender.get("category"),
                tender.get("cpv_code"), tender.get("cpv_description"),
                tender.get("location"), tender.get("procurement_method"),
                tender.get("is_sme_friendly", 0)
            ))
            await db.commit()
            return True
    finally:
        await db.close()


async def get_tenders(
    search: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    min_score: Optional[int] = None,
    status: Optional[str] = None,
    nhs_software: bool = False,
    is_sme_friendly: bool = False,
    location: Optional[str] = None,
    sort_by: str = "published_at",
    sort_order: str = "DESC",
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[dict], int]:
    """Get matching tenders with pagination and total count."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        conditions = []
        params = []
        
        if nhs_software:
            conditions.append("(buyer LIKE ? OR title LIKE ?) AND category = 'Technology'")
            params.extend(['%NHS%', '%NHS%'])
        
        if search:
            conditions.append("(title LIKE ? OR description LIKE ? OR buyer LIKE ?)")
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])
            
        if is_sme_friendly:
            conditions.append("is_sme_friendly = 1")
            
        if location:
            conditions.append("location LIKE ?")
            params.append(f"%{location}%")

        if category:
            conditions.append("category = ?")
            params.append(category)

        if source:
            conditions.append("source = ?")
            params.append(source)

        if min_score is not None:
            conditions.append("relevance_score >= ?")
            params.append(min_score)

        if status:
            conditions.append("status = ?")
            params.append(status)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Validate sort_by
        allowed_sorts = {"published_at", "relevance_score", "budget_amount", "deadline", "title"}
        if sort_by not in allowed_sorts:
            sort_by = "published_at"
        sort_order = "ASC" if sort_order.upper() == "ASC" else "DESC"

        # Count total
        count_cursor = await db.execute(
            f"SELECT COUNT(*) FROM tenders WHERE {where_clause}", params
        )
        total = (await count_cursor.fetchone())[0]

        # Get page
        offset = (page - 1) * per_page
        cursor = await db.execute(
            f"""SELECT * FROM tenders WHERE {where_clause}
                ORDER BY {sort_by} {sort_order}
                LIMIT ? OFFSET ?""",
            params + [per_page, offset]
        )
        rows = await cursor.fetchall()
        tenders = [dict(row) for row in rows]

        return tenders, total


async def get_tender_by_id(tender_id: int) -> Optional[dict]:
    """Get a single tender by ID."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM tenders WHERE id = ?", (tender_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_stats() -> dict:
    """Get dashboard statistics."""
    db = await get_db()
    try:
        stats = {}

        cursor = await db.execute("SELECT COUNT(*) FROM tenders")
        stats["total"] = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM tenders WHERE status IN ('open', 'active')"
        )
        stats["active"] = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM tenders WHERE relevance_score >= 6"
        )
        stats["high_relevance"] = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(DISTINCT source) FROM tenders"
        )
        stats["sources"] = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(DISTINCT category) FROM tenders WHERE category IS NOT NULL"
        )
        stats["categories"] = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT category, COUNT(*) as count FROM tenders
               WHERE category IS NOT NULL
               GROUP BY category ORDER BY count DESC LIMIT 8"""
        )
        stats["by_category"] = [dict(row) for row in await cursor.fetchall()]

        return stats
    finally:
        await db.close()


async def get_unnotified_tenders(min_score: int = 6) -> list[dict]:
    """Get tenders that haven't been notified yet and meet the score threshold."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM tenders
               WHERE notified = 0 AND relevance_score >= ?
               ORDER BY relevance_score DESC""",
            (min_score,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def mark_as_notified(tender_ids: list[int]):
    """Mark tenders as notified."""
    db = await get_db()
    try:
        placeholders = ",".join("?" * len(tender_ids))
        await db.execute(
            f"UPDATE tenders SET notified = 1 WHERE id IN ({placeholders})",
            tender_ids
        )
        await db.commit()
    finally:
        await db.close()


async def get_setting(key: str) -> Optional[str]:
    """Get a setting by key."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None
    finally:
        await db.close()


async def set_setting(key: str, value: str):
    """Set a setting value."""
    db = await get_db()
    try:
        await db.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        """, (key, value))
        await db.commit()
    finally:
        await db.close()

