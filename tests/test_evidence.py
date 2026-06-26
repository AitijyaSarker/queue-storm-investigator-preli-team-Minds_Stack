"""Evidence reasoning tests."""
from app.schemas.request import AnalyzeRequest, TransactionEntry
from app.services.investigator import investigate


def test_amount_matching_picks_correct_txn():
    history = [
        TransactionEntry(
            transaction_id="TXN-A", timestamp="2026-04-14T09:00:00Z",
            type="transfer", amount=200, counterparty="+8801711111111", status="completed",
        ),
        TransactionEntry(
            transaction_id="TXN-B", timestamp="2026-04-14T14:08:22Z",
            type="transfer", amount=5000, counterparty="+8801722222222", status="completed",
        ),
    ]
    req = AnalyzeRequest(
        ticket_id="TKT-007",
        complaint="I accidentally sent 5000 taka to a wrong number around 2pm.",
        transaction_history=history,
    )
    r = investigate(req)
    assert r.relevant_transaction_id == "TXN-B"
    assert r.evidence_verdict.value == "consistent"


def test_empty_history_returns_null():
    req = AnalyzeRequest(ticket_id="TKT-008", complaint="Wrong number 5000 taka at 2pm.")
    r = investigate(req)
    assert r.relevant_transaction_id is None
    assert r.evidence_verdict.value == "insufficient_data"


def test_pending_payment_failed_consistent():
    txn = TransactionEntry(
        transaction_id="TXN-P", timestamp="2026-04-14T12:00:00Z",
        type="payment", amount=1500, counterparty="MERCHANT-X", status="pending",
    )
    req = AnalyzeRequest(
        ticket_id="TKT-009",
        complaint="Payment failed but money was deducted.",
        transaction_history=[txn],
    )
    r = investigate(req)
    # pending -> insufficient; but case_type still payment_failed
    assert r.case_type.value == "payment_failed"
    assert r.evidence_verdict.value == "insufficient_data"
