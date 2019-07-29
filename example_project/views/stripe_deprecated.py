from dataclasses import asdict
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from structlog import get_logger

from payment import get_payment_gateway
from payment.gateways.stripe import get_amount_for_stripe
from payment.models import Payment
from payment.utils import create_payment_information, gateway_authorize
from payment.utils import gateway_process_payment

logger = get_logger()


def authorize_and_capture_old_checkout(request: HttpRequest, payment_id: int) -> HttpResponse:
    return _pay(request, payment_id, True)


def authorize_old_checkout(request: HttpRequest, payment_id: int) -> HttpResponse:
    return _pay(request, payment_id, False)


def _pay(request: HttpRequest, payment_id: int, also_capture: bool) -> HttpResponse:
    payment = get_object_or_404(Payment, id=payment_id)
    payment_data = create_payment_information(payment)

    logger.debug('stripe _pay payment-data', **asdict(payment_data))

    payment_gateway, gateway_config = get_payment_gateway(payment.gateway)

    connection_params = gateway_config.connection_params
    form = payment_gateway.create_form(
        request.POST or None,
        payment_information=payment_data,
        connection_params=connection_params,
    )
    if form.is_valid():
        try:
            if also_capture:
                logger.info('stripe gateway-process-payment', payment=payment)
                gateway_process_payment(payment=payment, payment_token=form.get_payment_token())
            else:
                logger.info('stripe authorize', payment=payment)
                gateway_authorize(payment=payment, payment_token=form.get_payment_token())
        except Exception as exc:
            form.add_error(None, str(exc))
        else:
            return redirect('view_payment', payment_id=payment.pk)

    client_token = payment_gateway.get_client_token(connection_params=connection_params)
    ctx = {
        "form": form,
        "payment": payment,
        "client_token": client_token,
    }
    return TemplateResponse(request, gateway_config.template_path, ctx)


@csrf_exempt
def authorize_old_checkout_ajax(request, payment_id: int) -> HttpResponse:
    if request.method == 'GET':
        payment_params_endpoint = reverse('stripe_payment_params', args=[payment_id])
        return TemplateResponse(
            request,
            'stripe/old_checkout_ajax.html',
            {'payment_params_endpoint': payment_params_endpoint})
    elif request.method == 'POST':
        payment = get_object_or_404(Payment, id=payment_id)
        payment_data = create_payment_information(payment)
        logger.debug('stripe payment-data', **asdict(payment_data))
        payment_gateway, gateway_config = get_payment_gateway(payment.gateway)
        connection_params = gateway_config.connection_params
        form = payment_gateway.create_form(
            request.POST,
            payment_information=payment_data,
            connection_params=connection_params)
        if form.is_valid():
            try:
                logger.info('stripe authorize', payment=payment)
                gateway_authorize(payment=payment, payment_token=form.get_payment_token())
            except Exception as exc:
                form.add_error(None, str(exc))
                logger.error('stripe authorize', exc_info=exc)
                return HttpResponse('Error authorizing {}: {}'.format(payment_id, exc))
            else:
                return redirect('view_payment', payment_id=payment.pk)


@api_view(['GET'])
def payment_params(request, payment_id: int) -> HttpResponse:
    """
    Returns a data representation of the parameters that are needed to initiate a stripe payment.
    This is not part of the gateway abstraction, so we implement it directly using the stripe API
    """
    payment = get_object_or_404(Payment, id=payment_id)

    _, gateway_config = get_payment_gateway(payment.gateway)
    gateway_params = gateway_config.connection_params

    amount = payment.total.amount
    currency = payment.total.currency.code

    stripe_payment_params = {
        "key": gateway_params.get("public_key"),
        "amount": get_amount_for_stripe(amount, currency),
        "name": gateway_params.get("store_name"),
        "currency": currency,
        "locale": "auto",
        "allow-remember-me": "false",
        "billing-address": "false",
        "zip-code": "false",
        "email": payment.customer_email
    }

    image = gateway_params.get("store_image")
    if image:
        payment_params["image"] = image

    result = {
        "gateway": payment.gateway,
        "params": stripe_payment_params,
    }

    return JsonResponse(result)
