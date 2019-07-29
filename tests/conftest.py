import pytest
from moneyed import Money

from payment import TransactionKind, ChargeStatus
from payment.models import Payment


@pytest.fixture
def payment_dummy(db, settings):
    return Payment.objects.create(
        gateway=settings.DUMMY,
        total=Money(80, 'USD'),
        captured_amount=Money(0, 'USD'),
        customer_email='test@example.com',
    )


@pytest.fixture
def payment_txn_preauth(payment_dummy):
    payment = payment_dummy
    payment.save()

    payment.transactions.create(
        amount=payment.total,
        kind=TransactionKind.AUTH,
        gateway_response={},
        is_success=True,
    )
    return payment


@pytest.fixture
def payment_txn_captured(payment_dummy):
    payment = payment_dummy
    payment.charge_status = ChargeStatus.FULLY_CHARGED
    payment.captured_amount = payment.total
    payment.save()

    payment.transactions.create(
        amount=payment.total,
        kind=TransactionKind.CAPTURE,
        gateway_response={},
        is_success=True,
    )
    return payment


@pytest.fixture
def payment_txn_refunded(payment_dummy):
    payment = payment_dummy
    payment.charge_status = ChargeStatus.FULLY_REFUNDED
    payment.is_active = False
    payment.save()

    payment.transactions.create(
        amount=payment.total,
        kind=TransactionKind.REFUND,
        gateway_response={},
        is_success=True,
    )
    return payment


@pytest.fixture
def payment_not_authorized(payment_dummy):
    payment_dummy.is_active = False
    payment_dummy.save()
    return payment_dummy
