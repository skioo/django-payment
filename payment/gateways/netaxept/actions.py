from django.db import transaction
from structlog import get_logger

from payment import get_payment_gateway, TransactionKind
from payment.gateways.netaxept import NetaxeptProtocolError
from payment.gateways.netaxept import netaxept_protocol, gateway_to_netaxept_config
from payment.models import Payment, Transaction

logger = get_logger()


class NetaxeptException(Exception):
    pass


class PaymentAlreadyRegisteredAndAuthorized(NetaxeptException):
    def __str__(self):
        return 'Payment already registered and authorized'


def register_payment(payment: Payment) -> str:
    """
    This part of the process is unique to netaxept so it cannot be implemented inside the
    payment generic SPI. This implies that a programmer who wants to use the netaxept gateway will have to know
    to call this specific function.

    This function:

    - Registers the payment with netaxept
    - Stores the newly created netaxept transaction_id in the Payment (the transaction_id represents the payment on
       the netaxept side, and needs to be passed to netaxept for further operations like capturing, refunding, etc)
    - Create a Transaction object representing the registration for auditing purposes.

    :param payment: A payment to register
    :return: The the newly created netaxept transaction id
    :raises NetaxeptException: If the payment was already registered or the registration fails
    """
    logger.info('netaxept-actions-register', payment_id=payment.id)

    if payment.token != '':  # The payment was already registered.
        if payment.is_authorized:
            raise PaymentAlreadyRegisteredAndAuthorized()
        else:
            # If payment was registered but not yet authorized we re-register it so that a later authorize can succeeed:
            # Otherwise when the user gets to the netaxept terminal page he sees a 'payment already processed' error.
            logger.info('netaxept-regegister-payment', payment_id=payment.id)

    _payment_gateway, gateway_config = get_payment_gateway(payment.gateway)
    netaxept_config = gateway_to_netaxept_config(gateway_config)

    try:
        register_response = netaxept_protocol.register(
            config=netaxept_config,
            order_number=payment.id,
            amount=payment.total,
            language='en',
            customer_email=payment.customer_email)
    except NetaxeptProtocolError as exception:
        Transaction.objects.create(
            payment=payment,
            kind=TransactionKind.REGISTER,
            token='',
            is_success=False,
            amount=payment.total,
            error=exception.error,
            gateway_response=exception.raw_response)
        raise NetaxeptException(exception.error)

    with transaction.atomic():
        payment.token = register_response.transaction_id
        payment.save()

        Transaction.objects.create(
            payment=payment,
            kind=TransactionKind.REGISTER,
            token=register_response.transaction_id,
            is_success=True,
            amount=payment.total,
            error=None,
            gateway_response=register_response.raw_response)

    return register_response.transaction_id
