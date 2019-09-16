"""
Example views for interactive testing of payment with netaxept.
"""

from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path
from django.views.decorators.http import require_GET
from structlog import get_logger

from payment import get_payment_gateway
from payment.gateways.netaxept import actions
from payment.gateways.netaxept import gateway_to_netaxept_config
from payment.gateways.netaxept import netaxept_protocol
from payment.models import Payment
from payment.utils import gateway_authorize

logger = get_logger()


@require_GET
def register_and_goto_terminal(request: HttpRequest, payment_id: int) -> HttpResponse:
    """
    Register the payment with netaxept, and take the user to the terminal page for payment authorization.
    """
    logger.info('netaxept-register-and-goto-terminal', payment_id=payment_id)

    payment = get_object_or_404(Payment, id=payment_id)

    transaction_id = actions.register_payment(payment)

    payment_gateway, gateway_config = get_payment_gateway(payment.gateway)
    netaxept_config = gateway_to_netaxept_config(gateway_config)
    return redirect(netaxept_protocol.get_payment_terminal_url(config=netaxept_config, transaction_id=transaction_id))


@require_GET
def after_terminal(request):
    """
    The browser gets redirected here when the user finishes interacting with the netaxept terminal pages.
    We expect query-string parameters: transactionId and responseCode.
    https://shop.nets.eu/web/partners/response-codes

    Note that it is very easy for a user to invoke this endpoint himself (by looking at the parameters of the
    netaxept terminal in order to pretend that he paid.
    This is why we verify the state of the payment by calling netaxept.

    Assumptions: We expect the terminal to have been opened with AuthAuth set to True.
    """
    transaction_id = request.GET['transactionId']
    response_code = request.GET['responseCode']
    logger.info('netaxept-after-terminal', transaction_id=transaction_id, response_code=response_code)

    if response_code == 'OK':
        payment = Payment.objects.get(token=transaction_id)
        try:
            # This will verify if the payment was indeed authorized.
            gateway_authorize(payment=payment, payment_token=payment.token)
        except Exception as exc:
            logger.error('netaxept-after-terminal-error', exc_info=exc)
            return HttpResponse('Error authorizing {}: {}'.format(payment.id, exc))
        else:
            return redirect('view_payment', payment_id=payment.id)
    elif response_code == 'Cancel':
        return HttpResponse('Payment cancelled')
    else:
        return HttpResponse('Payment error {}'.format(response_code))


def query(request: HttpRequest, transaction_id: str) -> HttpResponse:
    """
    Retries the status of the given transaction from netaxept.
    """
    logger.info('netaxept-query', transaction_id=transaction_id)
    payment_gateway, gateway_config = get_payment_gateway('netaxept')
    netaxept_config = gateway_to_netaxept_config(gateway_config)
    query_response = netaxept_protocol.query(config=netaxept_config, transaction_id=transaction_id)
    return TemplateResponse(request, 'netaxept/query_result.html', {'query_response': query_response})


urls = [
    path('register_and_goto_terminal/<payment_id>', register_and_goto_terminal,
         name='netaxept_register_and_goto_terminal'),
    path('after_terminal', after_terminal, name='netaxept_after_terminal'),
    path('query/<transaction_id>', query, name='netaxept_query'),
]
