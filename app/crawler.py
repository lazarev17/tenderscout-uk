"""Crawlers for UK government tender sources using OCDS APIs."""

import httpx
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.filter_engine import calculate_relevance_score, classify_category
from app.database import upsert_tender

logger = logging.getLogger(__name__)

# Contracts Finder OCDS API
CF_BASE_URL = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"

# Find a Tender OCDS API
FTS_BASE_URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"


def parse_ocds_release(release: dict, source: str) -> Optional[dict]:
    """Parse a single OCDS release into our tender format."""
    try:
        tender_data = release.get("tender", {})
        if not tender_data:
            return None

        title = tender_data.get("title", "")
        if not title:
            return None

        description = tender_data.get("description", "")

        # Extract buyer
        buyer = ""
        buyer_info = release.get("buyer", {})
        if buyer_info:
            buyer = buyer_info.get("name", "")
        if not buyer:
            parties = release.get("parties", [])
            for party in parties:
                if "buyer" in party.get("roles", []):
                    buyer = party.get("name", "")
                    break

        # Extract budget/value
        budget_amount = None
        budget_currency = "GBP"
        value = tender_data.get("value", {})
        if value:
            budget_amount = value.get("amount")
            budget_currency = value.get("currency", "GBP")
        if not budget_amount:
            min_value = tender_data.get("minValue", {})
            if min_value:
                budget_amount = min_value.get("amount")
                budget_currency = min_value.get("currency", "GBP")

        # Extract deadline
        deadline = None
        tender_period = tender_data.get("tenderPeriod", {})
        if tender_period:
            deadline = tender_period.get("endDate")

        # Extract published date
        published_at = tender_data.get("datePublished") or release.get("date", "")

        # Status mapping
        status_map = {
            "planning": "planned",
            "active": "open",
            "complete": "closed",
            "cancelled": "cancelled",
            "unsuccessful": "closed",
            "withdrawn": "cancelled",
        }
        raw_status = tender_data.get("status", "active")
        status = status_map.get(raw_status, "open")

        # CPV classification
        cpv_code = None
        cpv_description = None
        classification = tender_data.get("classification", {})
        if classification.get("scheme") == "CPV":
            cpv_code = classification.get("id")
            cpv_description = classification.get("description")

        # Source URL
        source_url = ""
        ocid = release.get("ocid", "")
        if source == "Contracts Finder":
            # Build URL from the notice documents
            awards = release.get("awards", [])
            for award in awards:
                for doc in award.get("documents", []):
                    if doc.get("documentType") == "awardNotice":
                        source_url = doc.get("url", "")
                        break
            if not source_url:
                # Fallback: construct URL from OCID
                notice_id = release.get("id", "").split("-")[0] if release.get("id") else ""
                if notice_id:
                    source_url = f"https://www.contractsfinder.service.gov.uk/Notice/{notice_id}"
        elif source == "Find a Tender":
            if ocid:
                notice_id = ocid.replace("ocds-b5fd17-", "")
                source_url = f"https://www.find-tender.service.gov.uk/Notice/{notice_id}"

        # Location
        location = ""
        items = tender_data.get("items", [])
        for item in items:
            addrs = item.get("deliveryAddresses", [])
            for addr in addrs:
                location = addr.get("locality", "") or addr.get("region", "") or addr.get("postalCode", "")
                if location:
                    break
            if location:
                break
        if not location:
            parties = release.get("parties", [])
            for party in parties:
                if "buyer" in party.get("roles", []):
                    addr = party.get("address", {})
                    location = addr.get("locality", "") or addr.get("countryName", "")
                    break

        # Calculate relevance score
        relevance_score = calculate_relevance_score(
            title=title,
            description=description,
            buyer=buyer,
            budget_amount=budget_amount,
            cpv_code=cpv_code,
        )

        # Classify category
        category = classify_category(cpv_code, title, description)

        return {
            "ocid": ocid,
            "title": title,
            "description": description,
            "buyer": buyer,
            "budget_amount": budget_amount,
            "budget_currency": budget_currency,
            "deadline": deadline,
            "source": source,
            "source_url": source_url,
            "published_at": published_at,
            "relevance_score": relevance_score,
            "status": status,
            "category": category,
            "cpv_code": cpv_code,
            "cpv_description": cpv_description,
            "location": location,
            "procurement_method": tender_data.get("procurementMethodDetails", ""),
        }

    except Exception as e:
        logger.error(f"Error parsing OCDS release: {e}")
        return None


async def crawl_contracts_finder(days_back: int = 3) -> list[dict]:
    """
    Crawl Contracts Finder OCDS API for recent tenders.
    Returns list of new tenders that were inserted.
    """
    now = datetime.now(timezone.utc)
    published_from = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00Z")
    published_to = now.strftime("%Y-%m-%dT23:59:59Z")

    new_tenders = []
    page = 1

    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            params = {
                "publishedFrom": published_from,
                "publishedTo": published_to,
                "limit": 100,
                "stages": "tender,planning",
            }

            try:
                logger.info(f"Fetching Contracts Finder page {page}...")
                resp = await client.get(CF_BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Error fetching Contracts Finder: {e}")
                break

            releases = data.get("releases", [])
            if not releases:
                break

            for release in releases:
                tender = parse_ocds_release(release, "Contracts Finder")
                if tender:
                    is_new = await upsert_tender(tender)
                    if is_new:
                        new_tenders.append(tender)

            # Check for next page link
            links = data.get("links", {})
            next_url = links.get("next")
            if next_url:
                # Follow pagination
                try:
                    resp = await client.get(next_url)
                    resp.raise_for_status()
                    data = resp.json()
                    releases = data.get("releases", [])
                    if not releases:
                        break
                    for release in releases:
                        tender = parse_ocds_release(release, "Contracts Finder")
                        if tender:
                            is_new = await upsert_tender(tender)
                            if is_new:
                                new_tenders.append(tender)
                    page += 1
                    if page > 10:  # Safety limit
                        break
                except Exception as e:
                    logger.error(f"Error following pagination: {e}")
                    break
            else:
                break

    logger.info(f"Contracts Finder: found {len(new_tenders)} new tenders")
    return new_tenders


async def crawl_find_a_tender(days_back: int = 3) -> list[dict]:
    """
    Crawl Find a Tender OCDS API for recent tenders.
    Returns list of new tenders that were inserted.
    """
    now = datetime.now(timezone.utc)
    updated_from = (now - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00")
    updated_to = now.strftime("%Y-%m-%dT23:59:59")

    new_tenders = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        params = {
            "updatedFrom": updated_from,
            "updatedTo": updated_to,
        }

        try:
            logger.info("Fetching Find a Tender data...")
            resp = await client.get(FTS_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Error fetching Find a Tender: {e}")
            return new_tenders

        releases = data.get("releases", [])
        logger.info(f"Find a Tender: got {len(releases)} releases")

        for release in releases:
            tender = parse_ocds_release(release, "Find a Tender")
            if tender:
                is_new = await upsert_tender(tender)
                if is_new:
                    new_tenders.append(tender)

    logger.info(f"Find a Tender: found {len(new_tenders)} new tenders")
    return new_tenders


async def run_all_crawlers(days_back: int = 3) -> list[dict]:
    """Run all crawlers and return new tenders."""
    logger.info("Starting tender crawl...")
    all_new = []

    cf_tenders = await crawl_contracts_finder(days_back)
    all_new.extend(cf_tenders)

    fts_tenders = await crawl_find_a_tender(days_back)
    all_new.extend(fts_tenders)

    logger.info(f"Total new tenders found: {len(all_new)}")
    return all_new
