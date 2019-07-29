import json
import logging
from functools import wraps

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from moneyed import Money
from typing import Optional

from . import (
    ChargeStatus,
    GatewayError,
    OperationType,
    PaymentError,
    TransactionKind,
    get_payment_gateway,
)
from .interface import GatewayResponse, PaymentData, AddressData
from .models import Payment, Transaction

logger = logging.getLogger(__name__)

GENERIC_TRANSACTION_ERROR = "Transaction was unsuccessful"
REQUIRED_GATEWAY_KEYS = {
    "transaction_id",
    "is_success",
    "kind",
    "error",
    "amount",
    "currency",
}

ALLOWED_GATEWAY_KINDS = {choices[0] for choices in TransactionKind.CHOICES}


def get_gateway_operation_func(gateway, operation_type):
    """Return gateway method based on the operation type to be performed."""
    if operation_type == OperationType.PROCESS_PAYMENT:
        return gateway.process_payment
    if operation_type == OperationType.AUTH:
        return gateway.authorize
    if operation_type == OperationType.CAPTURE:
        return gateway.capture
    if operation_type == OperationType.VOID:
        return gateway.void
    if operation_type == OperationType.REFUND:
        return gateway.refund


def create_payment_information(
        payment: Payment,
        payment_token: Optional[str] = None,
        amount: Money = None,
        billing_address: AddressData = None,
        shipping_address: AddressData = None,
) -> PaymentData:
    """Extracts order information along with payment details.

    Returns information required to process payment and additional
    billing/shipping addresses for optional fraud-prevention mechanisms.
    """

    # PATCH: order_id = payment.order.pk if payment.order else None
    order_id = None

    if amount is None:
        amount = payment.total

    return PaymentData(  # type:ignore
        token=payment_token,  # The contract is not clear, is this optional or not?
        amount=amount.amount,
        currency=amount.currency.code,
        billing=billing_address,
        shipping=shipping_address,
        order_id=order_id,
        customer_ip_address=payment.customer_ip_address,
        customer_email=payment.customer_email,
        metadata=payment.metadata,
    )


def require_active_payment(view):
    """Require an active payment instance.

    Decorate a view to check if payment is authorized, so any actions
    can be performed on it.
    """

    @wraps(view)
    def func(payment: Payment, *args, **kwargs):
        if not payment.is_active:
            raise PaymentError("This payment is no longer active.")
        return view(payment, *args, **kwargs)

    return func


def create_transaction(
        payment: Payment,
        kind: str,
        payment_information: PaymentData,
        gateway_response: GatewayResponse = None,
        error_msg=None,
) -> Transaction:
    """Create a transaction based on transaction kind and gateway response."""

    # Default values for token, amount, currency are only used in cases where
    # response from gateway was invalid or an exception occured
    if not gateway_response:
        gateway_response = GatewayResponse(
            kind=kind,
            transaction_id=payment_information.token,
            is_success=False,
            amount=payment_information.amount,
            currency=payment_information.currency,
            error=error_msg,
            raw_response={},
        )

    return Transaction.objects.create(
        payment=payment,
        kind=gateway_response.kind,
        token=gateway_response.transaction_id,
        is_success=gateway_response.is_success,
        amount=Money(gateway_response.amount, gateway_response.currency),
        error=gateway_response.error,
        gateway_response=gateway_response.raw_response or {},
    )


def gateway_get_client_token(gateway_name: str):
    """Gets client token, that will be used as a customer's identificator for
    client-side tokenization of the chosen payment method.
    """
    gateway, gateway_config = get_payment_gateway(gateway_name)
    return gateway.get_client_token(config=gateway_config)


def clean_capture(payment: Payment, amount: Money):
    """Check if payment can be captured."""
    if amount.amount <= 0:
        raise PaymentError("Amount should be a positive number.")
    if not payment.can_capture():
        raise PaymentError("This payment cannot be captured.")
    if amount > payment.total or amount > (payment.total - payment.captured_amount):
        raise PaymentError("Unable to charge more than un-captured amount.")


def clean_authorize(payment: Payment):
    """Check if payment can be authorized."""
    if not payment.can_authorize():
        raise PaymentError("Charged transactions cannot be authorized again.")


def call_gateway(operation_type, payment, payment_token, **extra_params):
    """Helper that calls the passed gateway function and handles exceptions.

    Additionally does validation of the returned gateway response.
    """
    gateway, gateway_config = get_payment_gateway(payment.gateway)
    gateway_response = None
    error_msg = None

    payment_information = create_payment_information(
        payment, payment_token, **extra_params
    )

    try:
        func = get_gateway_operation_func(gateway, operation_type)
    except AttributeError:
        error_msg = "Gateway doesn't implement {} operation".format(operation_type.name)
        logger.exception(error_msg)
        raise PaymentError(error_msg)

    # The transaction kind is provided as a default value
    # for creating transactions when gateway has invalid response
    # The PROCESS_PAYMENT operation has CAPTURE as default transaction kind
    # For other operations, the transaction kind is same wtih operation type
    default_transaction_kind = TransactionKind.CAPTURE
    if operation_type != OperationType.PROCESS_PAYMENT:
        default_transaction_kind = getattr(
            TransactionKind, OperationType(operation_type).name
        )

    # Validate the default transaction kind
    if default_transaction_kind not in dict(TransactionKind.CHOICES):
        error_msg = "The default transaction kind is invalid"
        logger.exception(error_msg)
        raise PaymentError(error_msg)

    try:
        gateway_response = func(
            payment_information=payment_information, config=gateway_config
        )
        validate_gateway_response(gateway_response)
    except GatewayError:
        error_msg = "Gateway response validation failed"
        logger.exception(error_msg)
        gateway_response = None  # Set response empty as the validation failed
    except Exception as e:
        error_msg = 'Gateway encountered an error {}'.format(e)
        logger.exception(error_msg)
    finally:
        payment_transaction = create_transaction(
            payment=payment,
            kind=default_transaction_kind,
            payment_information=payment_information,
            error_msg=error_msg,
            gateway_response=gateway_response,
        )

    if not payment_transaction.is_success:
        # Attempt to get errors from response, if none raise a generic one
        raise PaymentError(payment_transaction.error or GENERIC_TRANSACTION_ERROR)

    return payment_transaction


def validate_gateway_response(response: GatewayResponse):
    """Validates response to be a correct format for Us to process."""

    if not isinstance(response, GatewayResponse):
        raise GatewayError("Gateway needs to return a GatewayResponse obj")

    if response.kind not in ALLOWED_GATEWAY_KINDS:
        raise GatewayError("Gateway response kind must be one of {}".format(sorted(ALLOWED_GATEWAY_KINDS)))

    try:
        json.dumps(response.raw_response, cls=DjangoJSONEncoder)
    except (TypeError, ValueError):
        raise GatewayError("Gateway response needs to be json serializable")


@transaction.atomic
def _gateway_postprocess(transaction, payment):
    transaction_kind = transaction.kind

    if transaction_kind == TransactionKind.CAPTURE:
        if payment.captured_amount is not None:
            payment.captured_amount += transaction.amount
        else:
            payment.captured_amount = transaction.amount

        if payment.get_charge_amount().amount <= 0:
            payment.charge_status = ChargeStatus.FULLY_CHARGED
        else:
            payment.charge_status = ChargeStatus.PARTIALLY_CHARGED

        payment.save()

    elif transaction_kind == TransactionKind.VOID:
        payment.is_active = False
        payment.save()

    elif transaction_kind == TransactionKind.REFUND:
        payment.captured_amount -= transaction.amount
        payment.charge_status = ChargeStatus.PARTIALLY_REFUNDED
        if payment.captured_amount.amount <= 0:
            payment.charge_status = ChargeStatus.FULLY_REFUNDED
            payment.is_active = False
        payment.save()


@require_active_payment
def gateway_process_payment(payment: Payment, payment_token: str, **extras) -> Transaction:
    """Performs whole payment process on a gateway."""
    transaction = call_gateway(
        operation_type=OperationType.PROCESS_PAYMENT,
        payment=payment,
        payment_token=payment_token,
        **extras,
    )

    _gateway_postprocess(transaction, payment)
    return transaction


@require_active_payment
def gateway_authorize(payment: Payment, payment_token: str) -> Transaction:
    """Authorizes the payment and creates relevant transaction.

    Args:
     - payment_token: One-time-use reference to payment information.
    """
    clean_authorize(payment)
    return call_gateway(operation_type=OperationType.AUTH, payment=payment, payment_token=payment_token)


@require_active_payment
def gateway_capture(payment: Payment, amount: Money = None) -> Transaction:
    """Captures the money that was reserved during the authorization stage."""
    if amount is None:
        amount = payment.get_charge_amount()
    clean_capture(payment, amount)

    auth_transaction = payment.transactions.filter(
        kind=TransactionKind.AUTH, is_success=True
    ).first()
    if auth_transaction is None:
        raise PaymentError("Cannot capture unauthorized transaction")
    payment_token = auth_transaction.token

    transaction = call_gateway(
        operation_type=OperationType.CAPTURE,
        payment=payment,
        payment_token=payment_token,
        amount=amount,
    )

    _gateway_postprocess(transaction, payment)
    return transaction


@require_active_payment
def gateway_void(payment) -> Transaction:
    if not payment.can_void():
        raise PaymentError("Only pre-authorized transactions can be voided.")

    auth_transaction = payment.transactions.filter(
        kind=TransactionKind.AUTH, is_success=True
    ).first()
    if auth_transaction is None:
        raise PaymentError("Cannot void unauthorized transaction")
    payment_token = auth_transaction.token

    transaction = call_gateway(
        operation_type=OperationType.VOID, payment=payment, payment_token=payment_token
    )

    _gateway_postprocess(transaction, payment)
    return transaction


@require_active_payment
def gateway_refund(payment, amount: Money = None) -> Transaction:
    """Refunds the charged funds back to the customer.
    Refunds can be total or partial.
    """
    if amount is None:
        # If no amount is specified, refund the maximum possible
        amount = payment.captured_amount

    if not payment.can_refund():
        raise PaymentError("This payment cannot be refunded.")

    if amount.amount <= 0:
        raise PaymentError("Amount should be a positive number.")
    if amount > payment.captured_amount:
        raise PaymentError("Cannot refund more than captured")

    transaction = payment.transactions.filter(
        kind=TransactionKind.CAPTURE, is_success=True
    ).first()
    if transaction is None:
        raise PaymentError("Cannot refund uncaptured transaction")
    payment_token = transaction.token

    transaction = call_gateway(
        operation_type=OperationType.REFUND,
        payment=payment,
        payment_token=payment_token,
        amount=amount,
    )

    _gateway_postprocess(transaction, payment)
    return transaction
