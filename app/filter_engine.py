"""Keyword-based relevance scoring engine for UK tenders."""

import re
from typing import Optional

# IT / Software keywords
IT_KEYWORDS = [
    "software development", "software engineering", "digital platform",
    "digital service", "digital transformation", "it services",
    "information technology", "ict", "saas", "cloud services",
    "cloud computing", "data platform", "data analytics",
    "artificial intelligence", "machine learning", "ai ", " ai,",
    "deep learning", "automation", "cybersecurity", "cyber security",
    "web development", "web application", "mobile app",
    "application development", "devops", "infrastructure",
    "managed services", "technical support", "it support",
    "database", "api", "microservices", "agile",
    "digital workplace", "erp", "crm", "business intelligence",
]

# Healthcare keywords
HEALTH_KEYWORDS = [
    "healthcare", "health care", "health service",
    "nhs", "national health service", "patient system",
    "patient management", "electronic health record", "ehr",
    "electronic patient record", "epr", "clinical system",
    "clinical software", "medical software", "medical device",
    "telemedicine", "telehealth", "remote care",
    "health informatics", "health tech", "healthtech",
    "pharmacy", "pharmaceutical", "mental health",
    "social care", "care management", "hospital",
    "diagnostic", "pathology", "radiology",
    "gp system", "primary care", "secondary care",
]

# NHS and health-related buyers
NHS_BUYER_PATTERNS = [
    r"nhs", r"national health", r"health authority",
    r"clinical commissioning", r"integrated care",
    r"hospital", r"medical", r"health trust",
    r"department of health", r"dhsc",
    r"nice\b", r"health education england",
]

CATEGORY_MAP = {
    "72": "Technology",       # CPV 72 = IT services
    "48": "Technology",       # CPV 48 = Software
    "64": "Technology",       # CPV 64 = Telecommunications
    "85": "Healthcare",       # CPV 85 = Health services
    "33": "Healthcare",       # CPV 33 = Medical equipment
    "50": "Maintenance",
    "79": "Professional",
    "71": "Engineering",
    "45": "Construction",
    "90": "Environment",
    "80": "Education",
    "60": "Transport",
    "55": "Hospitality",
    "34": "Transport",
    "39": "Facility",
    "44": "Construction",
    "35": "Security",
    "38": "Research",
    "30": "Technology",       # CPV 30 = Office machinery
    "73": "Research",
    "92": "Recreation",
    "98": "Other Services",
    "15": "Food",
    "22": "Publishing",
    "18": "Clothing",
}


def classify_category(cpv_code: Optional[str], title: str = "", description: str = "") -> str:
    """Classify tender category based on CPV code and content."""
    if cpv_code:
        prefix = cpv_code[:2]
        if prefix in CATEGORY_MAP:
            return CATEGORY_MAP[prefix]

    # Fallback: keyword-based classification
    text = f"{title} {description}".lower()
    for kw in IT_KEYWORDS[:10]:
        if kw in text:
            return "Technology"
    for kw in HEALTH_KEYWORDS[:10]:
        if kw in text:
            return "Healthcare"

    return "Other"


def calculate_relevance_score(
    title: str,
    description: str,
    buyer: str,
    budget_amount: Optional[float] = None,
    cpv_code: Optional[str] = None,
) -> int:
    """
    Calculate relevance score for a tender based on spec criteria.

    Scoring:
    - Software/IT keywords found: +3 each (max +12)
    - Healthcare keywords found: +3 each (max +12)
    - NHS buyer: +4
    - Budget > £100k: +2
    - IT/Health CPV code: +3
    """
    score = 0
    text = f"{title} {description}".lower()
    buyer_lower = (buyer or "").lower()

    # IT keywords (max 4 matches = +12)
    it_matches = 0
    for kw in IT_KEYWORDS:
        if kw.lower() in text:
            it_matches += 1
            if it_matches >= 4:
                break
    score += it_matches * 3

    # Healthcare keywords (max 4 matches = +12)
    health_matches = 0
    for kw in HEALTH_KEYWORDS:
        if kw.lower() in text:
            health_matches += 1
            if health_matches >= 4:
                break
    score += health_matches * 3

    # NHS buyer bonus
    for pattern in NHS_BUYER_PATTERNS:
        if re.search(pattern, buyer_lower):
            score += 4
            break

    # Budget bonus
    if budget_amount and budget_amount > 100_000:
        score += 2

    # CPV code bonus (IT or Health category)
    if cpv_code:
        prefix = cpv_code[:2]
        if prefix in ("72", "48", "64", "30"):  # IT-related CPV
            score += 3
        elif prefix in ("85", "33"):  # Health-related CPV
            score += 3

    return score


def is_relevant(score: int, threshold: int = 3) -> bool:
    """Check if a tender meets the relevance threshold."""
    return score >= threshold
