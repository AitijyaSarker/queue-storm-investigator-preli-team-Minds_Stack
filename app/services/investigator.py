"""
Core investigator pipeline.

Steps:
1. Detect language & scrub prompt-injection from complaint.
2. Match keywords -> candidate case_types.
3. Match transaction -> relevant_transaction_id.
4. Decide evidence_verdict based on txn.status vs complaint narrative.
5. Choose severity from case_type + amount + risk signals.
6. Route department per Section 7.2.
7. Decide human_review_required (high-value, ambiguous, phishing, critical).
8. Build templated agent_summary, recommended_next_action, customer_reply.
9. Final safety guard on output strings.
"""
from __future__ import annotations

from typing import Optional

from app.core.enums import (
    CaseType,
    Department,
    EvidenceVerdict,
    Severity,
    TxnStatus,
)
from app.core.safety import (
    sanitize_customer_reply,
    sanitize_next_action,
    scrub_injection,
)
from app.schemas.request import AnalyzeRequest, TransactionEntry
from app.schemas.response import AnalyzeResponse
from app.utils.text import detect_language, find_hits
from app.utils.transaction import best_match, extract_amounts, extract_time_hints


# ---------- Classification helpers ----------

# Ordered priority for ambiguous complaints.
CASE_PRIORITY = [
    CaseType.PHISHING,
    CaseType.WRONG_TRANSFER,
    CaseType.PAYMENT_FAILED,
    CaseType.DUPLICATE_PAYMENT,
    CaseType.AGENT_CASH_IN_ISSUE,
    CaseType.MERCHANT_SETTLEMENT_DELAY,
    CaseType.REFUND_REQUEST,
]


def _classify_case(text: str) -> tuple[CaseType, list[str]]:
    hits = find_hits(text)
    if not hits:
        return CaseType.OTHER, ["no_keywords"]
    for case in CASE_PRIORITY:
        key = case.value
        if key in hits:
            return case, [key] + [f"kw:{kw[:30]}" for kw in hits[key][:2]]
    return CaseType.OTHER, ["fallback_other"]


def _severity_for(case: CaseType, amount: Optional[float], txn: Optional[TransactionEntry]) -> Severity:
    if case == CaseType.PHISHING:
        return Severity.CRITICAL
    if case == CaseType.WRONG_TRANSFER and amount and amount >= 5000:
        return Severity.HIGH
    if case == CaseType.WRONG_TRANSFER:
        return Severity.MEDIUM
    if case == CaseType.PAYMENT_FAILED and amount and amount >= 3000:
        return Severity.HIGH
    if case == CaseType.PAYMENT_FAILED:
        return Severity.MEDIUM
    if case == CaseType.REFUND_REQUEST and amount and amount >= 5000:
        return Severity.HIGH
    if case == CaseType.REFUND_REQUEST:
        return Severity.MEDIUM
    if case == CaseType.DUPLICATE_PAYMENT:
        return Severity.HIGH
    if case == CaseType.MERCHANT_SETTLEMENT_DELAY and amount and amount >= 10000:
        return Severity.HIGH
    if case == CaseType.AGENT_CASH_IN_ISSUE and amount and amount >= 3000:
        return Severity.HIGH
    if case == CaseType.OTHER:
        return Severity.LOW
    return Severity.MEDIUM


def _department_for(case: CaseType) -> Department:
    mapping = {
        CaseType.WRONG_TRANSFER: Department.DISPUTE_RESOLUTION,
        CaseType.PAYMENT_FAILED: Department.PAYMENTS_OPS,
        CaseType.REFUND_REQUEST: Department.DISPUTE_RESOLUTION,
        CaseType.DUPLICATE_PAYMENT: Department.PAYMENTS_OPS,
        CaseType.MERCHANT_SETTLEMENT_DELAY: Department.MERCHANT_OPERATIONS,
        CaseType.AGENT_CASH_IN_ISSUE: Department.AGENT_OPERATIONS,
        CaseType.PHISHING: Department.FRAUD_RISK,
        CaseType.OTHER: Department.CUSTOMER_SUPPORT,
    }
    return mapping[case]


def _evidence_verdict(case: CaseType, txn: Optional[TransactionEntry], text: str) -> EvidenceVerdict:
    if not txn:
        return EvidenceVerdict.INSUFFICIENT_DATA
    if case == CaseType.PAYMENT_FAILED:
        if txn.status == TxnStatus.FAILED:
            return EvidenceVerdict.CONSISTENT
        if txn.status == TxnStatus.COMPLETED:
            return EvidenceVerdict.INCONSISTENT
        return EvidenceVerdict.INSUFFICIENT_DATA
    if case == CaseType.WRONG_TRANSFER:
        if txn.status == TxnStatus.COMPLETED and txn.type.value == "transfer":
            return EvidenceVerdict.CONSISTENT
        return EvidenceVerdict.INCONSISTENT
    if case == CaseType.DUPLICATE_PAYMENT:
        # duplicate is consistent if there are two similar completed transfers to same cp.
        return EvidenceVerdict.CONSISTENT if txn.status == TxnStatus.COMPLETED else EvidenceVerdict.INSUFFICIENT_DATA
    if case == CaseType.AGENT_CASH_IN_ISSUE:
        if txn.status == TxnStatus.COMPLETED:
            return EvidenceVerdict.INCONSISTENT
        if txn.status in {TxnStatus.PENDING, TxnStatus.FAILED}:
            return EvidenceVerdict.CONSISTENT
        return EvidenceVerdict.INSUFFICIENT_DATA
    if case == CaseType.MERCHANT_SETTLEMENT_DELAY:
        return EvidenceVerdict.CONSISTENT if txn.status in {TxnStatus.PENDING, TxnStatus.COMPLETED} else EvidenceVerdict.INSUFFICIENT_DATA
    if case == CaseType.REFUND_REQUEST:
        return EvidenceVerdict.CONSISTENT if txn.status in {TxnStatus.COMPLETED, TxnStatus.FAILED} else EvidenceVerdict.INSUFFICIENT_DATA
    if case == CaseType.PHISHING:
        return EvidenceVerdict.INSUFFICIENT_DATA
    return EvidenceVerdict.INSUFFICIENT_DATA


def _needs_human(case: CaseType, sev: Severity, verdict: EvidenceVerdict, amount: Optional[float]) -> bool:
    if case == CaseType.PHISHING:
        return True
    if sev == Severity.CRITICAL:
        return True
    if verdict == EvidenceVerdict.INSUFFICIENT_DATA:
        return True
    if verdict == EvidenceVerdict.INCONSISTENT:
        return True
    if case in {CaseType.WRONG_TRANSFER, CaseType.REFUND_REQUEST}:
        return True
    if amount and amount >= 5000:
        return True
    return False


def _confidence(case: CaseType, verdict: EvidenceVerdict, txn: Optional[TransactionEntry]) -> float:
    if verdict == EvidenceVerdict.INSUFFICIENT_DATA:
        return 0.45
    if case == CaseType.OTHER:
        return 0.55
    if txn is None:
        return 0.6
    return 0.85


# ---------- Templates ----------

def _money(amount: Optional[float]) -> str:
    if amount is None:
        return "the amount in question"
    if float(amount).is_integer():
        return f"{int(amount)} BDT"
    return f"{amount} BDT"


def _summary(case: CaseType, txn: Optional[TransactionEntry], amount: Optional[float]) -> str:
    txn_ref = f" related to transaction {txn.transaction_id}" if txn else ""
    money = _money(amount)
    msgs = {
        CaseType.WRONG_TRANSFER: f"Customer reports an erroneous transfer of {money}{txn_ref} sent to the wrong recipient.",
        CaseType.PAYMENT_FAILED: f"Customer reports a failed payment of {money}{txn_ref} where the balance appears to have been deducted.",
        CaseType.REFUND_REQUEST: f"Customer is requesting a refund of {money}{txn_ref}.",
        CaseType.DUPLICATE_PAYMENT: f"Customer reports being charged more than once for the same payment{txn_ref}.",
        CaseType.MERCHANT_SETTLEMENT_DELAY: f"Merchant reports settlement of {money}{txn_ref} has not been received.",
        CaseType.AGENT_CASH_IN_ISSUE: f"Customer reports an agent cash-in of {money}{txn_ref} was not reflected in their balance.",
        CaseType.PHISHING: "Customer reports a suspicious call, SMS, or social-engineering attempt requesting sensitive credentials.",
        CaseType.OTHER: f"Customer submitted a complaint{txn_ref} that does not clearly match a known case type.",
    }
    return msgs[case]


def _next_action(case: CaseType, txn: Optional[TransactionEntry], verdict: EvidenceVerdict) -> str:
    txn_id = txn.transaction_id if txn else "the referenced transaction"
    base = {
        CaseType.WRONG_TRANSFER: f"Verify {txn_id} details with the customer and initiate the standard wrong-transfer review process.",
        CaseType.PAYMENT_FAILED: f"Reconcile {txn_id} status with the payments ledger; if a duplicate debit is found, escalate to payments ops.",
        CaseType.REFUND_REQUEST: f"Review eligibility for {txn_id} through the official dispute process before any customer-facing commitment.",
        CaseType.DUPLICATE_PAYMENT: f"Audit {txn_id} and adjacent entries for duplicate debits and prepare a reconciliation report.",
        CaseType.MERCHANT_SETTLEMENT_DELAY: f"Check the settlement queue for {txn_id} and confirm the merchant payout schedule.",
        CaseType.AGENT_CASH_IN_ISSUE: f"Coordinate with the responsible agent to confirm the cash-in for {txn_id}.",
        CaseType.PHISHING: "Block the suspicious contact if possible and flag the customer account with a fraud-risk note.",
        CaseType.OTHER: f"Request additional details from the customer and review {txn_id} context.",
    }
    action = base[case]
    if verdict == EvidenceVerdict.INSUFFICIENT_DATA:
        action += " Pull additional transaction history before any decision."
    if verdict == EvidenceVerdict.INCONSISTENT:
        action += " Document the inconsistency and present evidence to a human reviewer."
    return action


def _customer_reply(case: CaseType, txn: Optional[TransactionEntry], amount: Optional[float]) -> str:
    money = _money(amount)
    txn_id = txn.transaction_id if txn else "your recent activity"
    if case == CaseType.PHISHING:
        return (
            "Thank you for reporting this. For your security, please do not share your PIN, OTP, password, "
            "or card details with anyone, and avoid clicking any links in suspicious messages. Our team will "
            "review your case and any eligible amount will be handled through official channels only. "
            "Please continue to use the official app for further updates."
        )
    if case == CaseType.WRONG_TRANSFER:
        return (
            f"Thank you for reaching out. We have noted your concern about transaction {txn_id} involving {money}. "
            "Our dispute team will verify the details through the standard process. Any eligible amount will be "
            "returned through official channels only. Please continue to use the official app for further updates."
        )
    if case == CaseType.PAYMENT_FAILED:
        return (
            f"We have noted your concern about transaction {txn_id} where {money} may have been deducted. "
            "Our payments team will reconcile the transaction against our ledger and update you. Any eligible "
            "amount will be returned through official channels only if the deduction is confirmed."
        )
    if case == CaseType.REFUND_REQUEST:
        return (
            f"Thank you for contacting us about {money} related to transaction {txn_id}. We have shared your "
            "request with our dispute team. Any eligible amount will be returned through official channels only "
            "after eligibility is confirmed."
        )
    if case == CaseType.DUPLICATE_PAYMENT:
        return (
            f"We have noted your concern about a possible duplicate charge of {money} on transaction {txn_id}. "
            "Our payments team will audit the related entries. Any eligible amount will be returned through "
            "official channels only."
        )
    if case == CaseType.MERCHANT_SETTLEMENT_DELAY:
        return (
            f"We have noted your settlement concern regarding {money} on transaction {txn_id}. Our merchant "
            "operations team will check the settlement queue and follow up through the official merchant portal."
        )
    if case == CaseType.AGENT_CASH_IN_ISSUE:
        return (
            f"We have noted your concern about an agent cash-in of {money} ({txn_id}) that was not reflected. "
            "Our agent operations team will coordinate with the responsible agent and confirm the deposit."
        )
    return (
        f"Thank you for reaching out. We have received your concern regarding {txn_id}. Our team will review "
        "your case and respond through official channels only."
    )


# ---------- Public entrypoint ----------

def investigate(req: AnalyzeRequest) -> AnalyzeResponse:
    raw = req.complaint
    clean = scrub_injection(raw)

    language = req.language.value if req.language else detect_language(clean)

    case_type, reason_codes = _classify_case(clean)
    amounts = extract_amounts(clean)
    hours = extract_time_hints(clean)
    amount = max(amounts) if amounts else None

    txn: Optional[TransactionEntry] = best_match(req.transaction_history, amounts, hours)
    verdict = _evidence_verdict(case_type, txn, clean)

    severity = _severity_for(case_type, amount, txn)
    department = _department_for(case_type)
    human = _needs_human(case_type, severity, verdict, amount)
    confidence = _confidence(case_type, verdict, txn)

    summary = _summary(case_type, txn, amount)
    action_raw = _next_action(case_type, txn, verdict)
    reply_raw = _customer_reply(case_type, txn, amount)

    # Final safety scrub — guarantees Section 8 compliance even if a template drifts.
    reply = sanitize_customer_reply(reply_raw)
    action = sanitize_next_action(action_raw)

    reason_codes.append(f"lang:{language}")
    if txn:
        reason_codes.append("transaction_match")
    else:
        reason_codes.append("no_transaction_match")
    reason_codes.append(f"verdict:{verdict.value}")

    return AnalyzeResponse(
        ticket_id=req.ticket_id,
        relevant_transaction_id=txn.transaction_id if txn else None,
        evidence_verdict=verdict,
        case_type=case_type,
        severity=severity,
        department=department,
        agent_summary=summary,
        recommended_next_action=action,
        customer_reply=reply,
        human_review_required=human,
        confidence=round(confidence, 2),
        reason_codes=reason_codes,
    )
