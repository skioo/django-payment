from structlog import get_logger

from . import netaxept_protocol
from .netaxept_protocol import NetaxeptConfig, NetaxeptOperation, NetaxeptProtocolError
from ... import TransactionKind
from ...interface import GatewayConfig, GatewayResponse, PaymentData

logger = get_logger()


def get_client_token(**_):
    """ Not implemented for netaxept gateway. """
    pass


def authorize(payment_information: PaymentData,
              config: GatewayConfig,
              should_capture: bool = False) -> GatewayResponse:
    """
    In the case of netaxept we use this SPI method to verify that the payment was authorized
    (authorization was done before when the user was taken to the netaxept terminal).

    As per the SPI we just need to return a GatewayResponse and the django-payment framework will take care of the rest
    (creating a Transaction object, updating the authorized flag of the payment, etc)

    :param payment_information: The payment that was authorized
    :param config: the gateway config
    :param should_capture: We ignore this because it is too late to choose if we want to capture or not.
    :return: A gateway response, both in case of success and failure.
    """
    logger.info('netaxept-authorize', payment_information=payment_information)

    netaxept_config = gateway_to_netaxept_config(config)

    try:
        query_response = netaxept_protocol.query(config=netaxept_config, transaction_id=payment_information.token)
        transaction_authorized = query_response.authorized
        error = None
    except NetaxeptProtocolError as exception:
        transaction_authorized = False
        error = exception.error

    return GatewayResponse(
        is_success=transaction_authorized,
        kind=TransactionKind.AUTH,
        amount=payment_information.amount,
        currency=payment_information.currency,
        transaction_id=payment_information.token,
        error=error,
        raw_response=query_response.raw_response)


def process_payment(payment_information: PaymentData, config: GatewayConfig) -> GatewayResponse:
    raise NotImplementedError()


def capture(payment_information: PaymentData, config: GatewayConfig) -> GatewayResponse:
    return _op(payment_information, config, NetaxeptOperation.CAPTURE, TransactionKind.CAPTURE)


def refund(payment_information: PaymentData, config: GatewayConfig) -> GatewayResponse:
    return _op(payment_information, config, NetaxeptOperation.CREDIT, TransactionKind.REFUND)


def void(payment_information: PaymentData, config: GatewayConfig) -> GatewayResponse:
    return _op(payment_information, config, NetaxeptOperation.ANNUL, TransactionKind.VOID)


def gateway_to_netaxept_config(gateway_config: GatewayConfig) -> NetaxeptConfig:
    return NetaxeptConfig(**gateway_config.connection_params)


def _op(payment_information: PaymentData, config: GatewayConfig,
        netaxept_operation: NetaxeptOperation,
        transaction_kind: str) -> GatewayResponse:
    try:
        process_result = netaxept_protocol.process(
            config=gateway_to_netaxept_config(config),
            transaction_id=payment_information.token,
            operation=netaxept_operation,
            amount=payment_information.amount)
        # We don't need to introspect anything inside the process_result: If no exception was thrown we immediately
        # know process ran successfully
        return GatewayResponse(
            is_success=True,
            kind=transaction_kind,
            amount=payment_information.amount,
            currency=payment_information.currency,
            transaction_id=payment_information.token,
            error=None,
            raw_response=process_result.raw_response
        )
    except NetaxeptProtocolError as exception:
        return GatewayResponse(
            is_success=False,
            kind=transaction_kind,
            amount=payment_information.amount,
            currency=payment_information.currency,
            transaction_id=payment_information.token,
            error=exception.error,
            raw_response=exception.raw_response
        )
