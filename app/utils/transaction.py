"""Transaction-history matchers."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, Optional

from app.schemas.request import TransactionEntry


_AMOUNT_RE = re.compile(r"\b(\d{2,7})\b")
_TIME_HINT_RE = re.compile(
    r"(\d{1,2})\s*(?::(\d{2}))?\s*(am|pm|AM|PM)?|around\s+(\d{1,2})(?:\s*(am|pm|AM|PM))?|today\s+at\s+(\d{1,2})"
)


def _to_hour(ts: str) -> Optional[int]:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).hour
    except Exception:
        return None


def extract_amounts(text: str) -> list[float]:
    return [float(m) for m in _AMOUNT_RE.findall(text)]


def extract_time_hints(text: str) -> list[int]:
    out: list[int] = []
    for m in _TIME_HINT_RE.finditer(text):
        for g in m.groups():
            if g and g.isdigit():
                h = int(g)
                if 0 <= h <= 23:
                    out.append(h)
    return out


def best_match(
    history: Iterable[TransactionEntry],
    complaint_amounts: list[float],
    complaint_hours: list[int],
) -> Optional[TransactionEntry]:
    """Pick the transaction most likely referenced by the complaint."""
    candidates = list(history)
    if not candidates:
        return None
    scored: list[tuple[int, TransactionEntry]] = []
    for txn in candidates:
        score = 0
        if complaint_amounts and abs(txn.amount - max(complaint_amounts)) < 0.01:
            score += 5
        if complaint_hours:
            txn_hour = _to_hour(txn.timestamp)
            if txn_hour is not None and any(abs(txn_hour - h) <= 1 for h in complaint_hours):
                score += 3
        if txn.status.value in {"completed", "failed", "reversed"}:
            score += 1
        scored.append((score, txn))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored[0][0] > 0 else None
