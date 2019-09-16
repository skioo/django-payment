"""
Example views for interactive testing of payment with netaxept.
"""
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import path
from django.views.decorators.http import require_GET
from structlog import get_logger

from payment import get_payment_gateway
from payment.gateways.netaxept import actions
from payment.gateways.netaxept import gateway_to_netaxept_config
from payment.gateways.netaxept.netaxept_protocol import get_payment_terminal_url
from payment.models import Payment

logger = get_logger()


@require_GET
def register_and_authorize(request: HttpRequest, payment_id: int) -> HttpResponse:
    """
    Register the payment with netaxept, and take the user to the terminal page for payment authorization.
    """
    logger.info('netaxept-register-and-authorize', payment_id=payment_id)

    transaction_id = actions.register_payment(payment_id)

    payment = get_object_or_404(Payment, id=payment_id)
    payment_gateway, gateway_config = get_payment_gateway(payment.gateway)
    netaxept_config = gateway_to_netaxept_config(gateway_config)
    return redirect(get_payment_terminal_url(config=netaxept_config, transaction_id=transaction_id))


@require_GET
def after_terminal(request):
    """
    The browser gets redirected here when the user finishes interacting with the netaxept terminal pages.
    We expect query-string parameters: transactionId and responseCode.
    See: https://shop.nets.eu/web/partners/response-codes

    We know we opened the terminal with AutoAuth set to True, so we interpret this callback to mean that an
    AUTH operation was performed. Netaxept does not provide any way to authenticate that the callback really comes
    from netaxept (other than them sending us a valid hard to guess 32 character long transaction_id), so we cannot
    be 100% sure of the information received.
    We decide to store the authorization operation nonetheless. If by any chance the information was faked we will
    detect it in the next step, when we try to capture the money.
    """
    transaction_id = request.GET['transactionId']
    response_code = request.GET['responseCode']
    logger.info('netaxept-webhook', transaction_id=transaction_id, response_code=response_code)

    success = (response_code == 'OK')

    actions.create_auth_transaction(transaction_id=transaction_id, success=success)

    if success:
        return HttpResponse('ok')
    elif response_code:
        return HttpResponse('response code {}'.format(response_code))


urls = [
    path('register_and_authorize/<payment_id>', register_and_authorize, name='netaxept_register_and_authorize'),
    path('after_terminal', after_terminal, name='netaxept_after_terminal'),
]
