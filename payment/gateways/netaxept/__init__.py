from .netaxept_protocol import NetaxeptConfig, NetaxeptOperation, process, NetaxeptProtocolError
from ... import OperationType
from ...interface import GatewayConfig, GatewayResponse, PaymentData


def get_client_token(**_):
    """ Not implemented for netaxept gateway. """
    pass


def authorize(payment_information: PaymentData,
              config: GatewayConfig,
              should_capture: bool = False) -> GatewayResponse:
    raise NotImplementedError()


def process_payment(payment_information: PaymentData, config: GatewayConfig) -> GatewayResponse:
    raise NotImplementedError()


def capture(payment_information: PaymentData, config: GatewayConfig) -> GatewayResponse:
    return _op(payment_information, config, OperationType.CAPTURE)


def refund(payment_information: PaymentData, config: GatewayConfig) -> GatewayResponse:
    return _op(payment_information, config, OperationType.REFUND)


def void(payment_information: PaymentData, config: GatewayConfig) -> GatewayResponse:
    return _op(payment_information, config, OperationType.VOID)


def gateway_to_netaxept_config(gateway_config: GatewayConfig) -> NetaxeptConfig:
    return NetaxeptConfig(**gateway_config.connection_params)


def _op(payment_information: PaymentData, config: GatewayConfig, operation_type: OperationType) -> GatewayResponse:
    try:
        process_result = process(
            config=gateway_to_netaxept_config(config),
            transaction_id=payment_information.token,
            operation=_operation_type_to_netaxept_op[operation_type],
            amount=payment_information.amount)
        # We don't need to introspect anything inside the process_result: If no exception was thrown we immediately
        # know process ran successfully
        return GatewayResponse(
            is_success=True,
            kind=operation_type.value,
            amount=payment_information.amount,
            currency=payment_information.currency,
            transaction_id=payment_information.token,
            error=None,
            raw_response=process_result.raw_response
        )
    except NetaxeptProtocolError as exception:
        return GatewayResponse(
            is_success=False,
            kind=operation_type.value,
            amount=payment_information.amount,
            currency=payment_information.currency,
            transaction_id=payment_information.token,
            error=exception.error,
            raw_response=exception.raw_response
        )


_operation_type_to_netaxept_op = {
    OperationType.AUTH: NetaxeptOperation.AUTH,
    OperationType.CAPTURE: NetaxeptOperation.CAPTURE,
    OperationType.VOID: NetaxeptOperation.ANNUL,
    OperationType.REFUND: NetaxeptOperation.CREDIT,
}
