"""Classification and routing tests."""
from app.schemas.request import AnalyzeRequest, TransactionEntry
from app.services.investigator import investigate


def _post(ticket_id: str, complaint: str, txn: TransactionEntry | None = None):
    return investigate(
        AnalyzeRequest(
            ticket_id=ticket_id,
            complaint=complaint,
            transaction_history=[txn] if txn else [],
        )
    )


def test_wrong_transfer_high_severity_5k():
    txn = TransactionEntry(
        transaction_id="TXN-9101",
        timestamp="2026-04-14T14:08:22Z",
        type="transfer",
        amount=5000,
        counterparty="+8801719876543",
        status="completed",
    )
    r = _post("TKT-001", "I sent 5000 taka to a wrong number around 2pm today.", txn)
    assert r.case_type.value == "wrong_transfer"
    assert r.severity.value == "high"
    assert r.department.value == "dispute_resolution"
    assert r.relevant_transaction_id == "TXN-9101"
    assert r.evidence_verdict.value == "consistent"
    assert r.human_review_required is True


def test_payment_failed_consistent():
    txn = TransactionEntry(
        transaction_id="TXN-2",
        timestamp="2026-04-14T11:30:00Z",
        type="payment",
        amount=2500,
        counterparty="MERCHANT-1",
        status="failed",
    )
    r = _post("TKT-002", "Payment failed but money was deducted from my account.", txn)
    assert r.case_type.value == "payment_failed"
    assert r.evidence_verdict.value == "consistent"
    assert r.department.value == "payments_ops"


def test_payment_failed_inconsistent_when_completed():
    txn = TransactionEntry(
        transaction_id="TXN-2",
        timestamp="2026-04-14T11:30:00Z",
        type="payment",
        amount=2500,
        counterparty="MERCHANT-1",
        status="completed",
    )
    r = _post("TKT-002b", "Payment failed but money was deducted from my account.", txn)
    assert r.evidence_verdict.value == "inconsistent"
    assert r.human_review_required is True


def test_phishing_routes_to_fraud_risk_critical():
    r = _post("TKT-003", "Someone called and asked for my OTP. Is this a scam?")
    assert r.case_type.value == "phishing_or_social_engineering"
    assert r.severity.value == "critical"
    assert r.department.value == "fraud_risk"
    assert r.human_review_required is True


def test_refund_request_routes_to_dispute_resolution():
    r = _post("TKT-004", "I want a refund for my order, please return my money.")
    assert r.case_type.value == "refund_request"
    assert r.department.value == "dispute_resolution"


def test_no_history_marks_insufficient_data():
    r = _post("TKT-005", "Money deducted but merchant says payment failed.")
    assert r.relevant_transaction_id is None
    assert r.evidence_verdict.value == "insufficient_data"
    assert r.human_review_required is True


def test_unknown_complaint_routes_to_customer_support():
    r = _post("TKT-006", "Hello, I have a general question about my account.")
    assert r.case_type.value == "other"
    assert r.department.value == "customer_support"
