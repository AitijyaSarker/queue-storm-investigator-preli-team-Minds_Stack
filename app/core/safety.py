"""
Safety guardrails. Auto-penalized violations per Section 8.

Two-stage defense:
1. Input scrub: strip prompt-injection patterns from complaint before reasoning.
2. Output guard: scan every customer_reply / recommended_next_action. On violation,
   substitute a safe canonical template. Never expose the violation.
"""
from __future__ import annotations

import re
from typing import Final

# Patterns that NEVER appear in customer-facing text.
FORBIDDEN_CUSTOMER_PHRASES: Final[tuple[str, ...]] = (
    r"\bpin\b",
    r"\botp\b",
    r"\bone[\s-]?time[\s-]?password\b",
    r"\bpassword\b",
    r"\bcard\s*number\b",
    r"\bcredit\s*card\b",
    r"\bdebit\s*card\b",
    r"\bcvv\b",
    r"\bsend\s+(?:me|us)\s+your\b",
    r"\bshare\s+your\s+(?:pin|otp|password|code)\b",
    r"\bverify\s+by\s+sending\b",
)

# Phrasing that sounds like an unauthorized refund/commitment.
FORBIDDEN_COMMITMENT_PHRASES: Final[tuple[str, ...]] = (
    r"\bwe\s+will\s+refund\b",
    r"\brefund\s+has\s+been\s+approved\b",
    r"\brefund\s+is\s+approved\b",
    r"\bwe\s+have\s+reversed\b",
    r"\baccount\s+has\s+been\s+unblocked\b",
    r"\bwe\s+will\s+reverse\b",
    r"\brecovery\s+is\s+done\b",
)

# Suspicious third-party contact patterns.
FORBIDDEN_THIRD_PARTY: Final[tuple[str, ...]] = (
    r"\bcontact\s+(?:the\s+)?(?:number|person|agent|guy)\b",
    r"\bcall\s+(?:back\s+)?(?:this|that|the)\s+number\b",
    r"\breach\s+out\s+to\s+(?:him|her|them|the\s+sender)\b",
)

INJECTION_PATTERNS: Final[tuple[str, ...]] = (
    r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
    r"disregard\s+(?:all\s+)?(?:previous|prior|above)",
    r"you\s+are\s+now\s+",
    r"system\s*:\s*",
    r"<\|.*?\|>",
)


def scrub_injection(text: str) -> str:
    """Strip prompt-injection attempts from user-supplied complaint text."""
    out = text
    for pat in INJECTION_PATTERNS:
        out = re.sub(pat, "[redacted-instruction]", out, flags=re.IGNORECASE)
    return out


def _has_any(text: str, patterns: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(re.search(p, lower, flags=re.IGNORECASE) for p in patterns)


def sanitize_customer_reply(reply: str) -> str:
    """Replace a customer_reply that violates safety rules with a safe canonical version."""
    if _has_any(reply, FORBIDDEN_CUSTOMER_PHRASES) or _has_any(
        reply, FORBIDDEN_COMMITMENT_PHRASES
    ) or _has_any(reply, FORBIDDEN_THIRD_PARTY):
        return (
            "We have received your concern. For your security, please do not share any PIN, "
            "OTP, password, or card details with anyone. Our team will review your case and "
            "any eligible amount will be returned through official channels only. "
            "Please continue to use the official app or verified support channels for further updates."
        )
    return reply


def sanitize_next_action(action: str) -> str:
    """Strip unauthorized refund/commitment language from operational next steps."""
    if _has_any(action, FORBIDDEN_COMMITMENT_PHRASES):
        return (
            "Verify transaction details and eligibility through the standard dispute process. "
            "Do not confirm any refund, reversal, or account change to the customer directly."
        )
    return action
