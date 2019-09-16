from django.db import transaction
from django.shortcuts import get_object_or_404

from payment import get_payment_gateway, TransactionKind
from payment.gateways.netaxept import NetaxeptProtocolError
from payment.gateways.netaxept import netaxept_protocol, gateway_to_netaxept_config
from payment.models import Payment, Transaction


class NetaxeptException(Exception):
    def __str__(self):
        return repr(self.msg)


class PaymentAlreadyRegistered(NetaxeptException):
    msg = 'Payment already registered'


def register_payment(payment_id: int) -> str:
    """
    - Registers the payment with netaxept.
    - Records a Transaction representing the registration.
    - Stores the newly created netaxept transaction_id in the Payment.

    :param payment_id: The id of a Payment object.
    :return: The newly created netaxept transaction_id
    :raises NetaxeptException: If the registration fails
    """
    payment = get_object_or_404(Payment, id=payment_id)

    if payment.token != '':
        raise PaymentAlreadyRegistered()

    _payment_gateway, gateway_config = get_payment_gateway(payment.gateway)
    netaxept_config = gateway_to_netaxept_config(gateway_config)

    try:
        register_response = netaxept_protocol.register(
            config=netaxept_config,
            order_number=payment_id,
            amount=payment.total,
            language='en')
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
        Transaction.objects.create(
            payment=payment,
            kind=TransactionKind.REGISTER,
            token=register_response.transaction_id,
            is_success=True,
            amount=payment.total,
            error=None,
            gateway_response=register_response.raw_response)

        payment.token = register_response.transaction_id
        payment.save()

    return register_response.transaction_id


def create_auth_transaction(transaction_id: str, success: bool) -> Transaction:
    """ Record the outcome of a netaxept auth transaction. """
    payment = Payment.objects.get(token=transaction_id)

    return Transaction.objects.create(
        payment=payment,
        kind=TransactionKind.AUTH,
        token=transaction_id,
        is_success=success,
        amount=payment.total,
        error=None,
        gateway_response={})
