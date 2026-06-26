"""Lightweight text utilities: language detection + keyword extraction."""
from __future__ import annotations

import re

# English keyword -> regex pattern. Case-insensitive.
EN_PATTERNS: dict[str, list[str]] = {
    "wrong_transfer": [
        r"wrong\s+number", r"wrong\s+(?:recipient|person)", r"sent\s+to\s+the\s+wrong",
        r"mistaken(?:ly)?\s+sent", r"by\s+mistake", r"transfer(?:red|)\s+(?:to|at)\s+(?:a\s+)?wrong",
        r"ভুল\s+নম্বর",  # Bangla fallback
        r"ভুল\s+মানুষ",
    ],
    "payment_failed": [
        r"payment\s+failed", r"transaction\s+failed", r"failed\s+but\s+deduct",
        r"deducted\s+but\s+(?:not\s+)?received", r"money\s+deducted",
        r"পেমেন্ট\s+ব্যর্থ", r"কেটে\s+গেছে",
    ],
    "refund_request": [
        r"\brefund\b", r"want\s+(?:my\s+)?money\s+back", r"return\s+(?:my\s+)?money",
        r"টাকা\s+ফেরত", r"রিফান্ড",
    ],
    "duplicate_payment": [
        r"charged\s+twice", r"double\s+charged", r"duplicate\s+(?:payment|charge)",
        r"two\s+times", r"দুইবার\s+কেটেছে",
    ],
    "merchant_settlement_delay": [
        r"merchant\s+(?:payment|settlement)", r"settlement\s+(?:not\s+)?received",
        r"shop\s+(?:payment|settlement)", r"দোকানের\s+সেটেলমেন্ট",
    ],
    "agent_cash_in_issue": [
        r"agent\s+(?:cash\s+in|deposit)", r"deposited?\s+through\s+(?:an?\s+)?agent",
        r"cash\s+in\s+(?:not|not\s+yet)\s+(?:received|reflected)",
        r"এজেন্ট\s+ক্যাশ\s+ইন",
    ],
    "phishing_or_social_engineering": [
        r"otp\s+(?:asked|requested|want)", r"someone\s+asked\s+(?:for\s+)?(?:my\s+)?(?:pin|otp|password)",
        r"got\s+a\s+call\s+asking", r"suspicious\s+(?:sms|call|message|link)",
        r"phish(?:ing)?", r"scam(?:mer)?", r"fake\s+(?:call|message|number|link)",
        r"ফিশিং", r"স্ক্যাম",
    ],
}

# Banglish transliteration triggers (lowercased).
BANGLISH_HINTS = (
    "taka", "tah", "bdt", "bochor", "din", "ami", "apni", "ki", "keno",
    "paisa", "dilo", "dilen", "pathaicho", "pathalam", "pathalen", "nebe", "nilam",
    "kaj", "hoy", "hocche", "hoise", "korlam", "korlen", "koren", "korbo",
    "valo", "khub", "ekhon", "ekhn", "din-er", "dinr", "bonanza", "boishakh",
)


def detect_language(text: str) -> str:
    """Return 'en', 'bn', or 'mixed'."""
    has_bn = bool(re.search(r"[\u0980-\u09FF]", text))
    lower = text.lower()
    has_banglish = any(w in lower for w in BANGLISH_HINTS)
    has_en = bool(re.search(r"[a-zA-Z]{3,}", text))
    if has_bn and (has_en or has_banglish):
        return "mixed"
    if has_bn or has_banglish:
        return "mixed" if has_en else "bn"
    return "en"


def find_hits(text: str) -> dict[str, list[str]]:
    """Return mapping case_type -> list of matched keywords."""
    hits: dict[str, list[str]] = {}
    for case_type, patterns in EN_PATTERNS.items():
        matched: list[str] = []
        for pat in patterns:
            m = re.findall(pat, text, flags=re.IGNORECASE)
            matched.extend(m)
        if matched:
            hits[case_type] = matched
    return hits
