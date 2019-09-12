from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from structlog import get_logger

from payment import get_payment_gateway
from payment.gateways.stripe import get_amount_for_stripe, get_currency_for_stripe
from payment.models import Payment
from payment.utils import gateway_authorize, gateway_capture, gateway_refund

logger = get_logger()


def capture(request: HttpRequest, payment_id: int) -> HttpResponse:
    payment = get_object_or_404(Payment, id=payment_id)
    capture_result = gateway_capture(payment=payment)
    logger.info('stripe capture', payment=payment, capture_result=capture_result)
    return redirect('view_payment', payment_id=payment_id)


def checkout(request: HttpRequest, payment_id: int) -> HttpResponse:
    """
    Takes the user to the stripe checkout page.
    This is not part of the gateway abstraction, so we implement it directly using the stripe API
    """
    payment = get_object_or_404(Payment, id=payment_id)

    import stripe
    stripe.api_key = 'sk_test_QWtEpnVswmgW9aUJkyKmEutp00dsgn2KAa'

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        customer_email=payment.customer_email,
        line_items=[{
            'name': 'Your order',
            'amount': get_amount_for_stripe(payment.total.amount, payment.total.currency.code),
            'currency': get_currency_for_stripe(payment.total.currency.code),
            'quantity': 1,
        }],
        payment_intent_data={
            'capture_method': 'manual',
        },
        success_url='https://example.com/success',
        cancel_url='https://example.com/cancel',
    )
    return TemplateResponse(request, 'stripe/checkout.html', {'CHECKOUT_SESSION_ID': session.id})


@csrf_exempt
def elements_token(request: HttpRequest, payment_id: int) -> HttpResponse:
    payment = get_object_or_404(Payment, id=payment_id)
    payment_gateway, gateway_config = get_payment_gateway(payment.gateway)
    connection_params = gateway_config.connection_params

    if request.method == 'GET':
        return TemplateResponse(
            request,
            'stripe/elements_token.html',
            {'stripe_public_key': connection_params['public_key']})
    elif request.method == 'POST':
        stripe_token = request.POST.get('stripeToken')
        if stripe_token is None:
            return HttpResponse('missing stripe token')
        try:
            logger.info('stripe authorize', payment=payment)
            gateway_authorize(payment=payment, payment_token=stripe_token)
        except Exception as exc:
            logger.error('stripe authorize', exc_info=exc)
            return HttpResponse('Error authorizing {}: {}'.format(payment_id, exc))
        else:
            return redirect('view_payment', payment_id=payment.pk)


def payment_intents_manual_flow(request: HttpRequest, payment_id: int) -> HttpResponse:
    payment = get_object_or_404(Payment, id=payment_id)
    payment_gateway, gateway_config = get_payment_gateway(payment.gateway)
    connection_params = gateway_config.connection_params

    stripe_public_key = connection_params['public_key']
    confirm_payment_endpoint = reverse('stripe_payment_intents_confirm_payment', args=[payment_id])

    return TemplateResponse(
        request,
        'stripe/payment_intents_manual_flow.html',
        {
            'stripe_public_key': stripe_public_key,
            'confirm_payment_endpoint': confirm_payment_endpoint})


def payment_intents_confirm_payment(request, payment_id):
    # XXX: Update the payment with the info
    payment = get_object_or_404(Payment, id=payment_id)
    payment_gateway, gateway_config = get_payment_gateway(payment.gateway)
    connection_params = gateway_config.connection_params
    stripe_public_key = connection_params['public_key']

    import stripe
    stripe.api_key = stripe_public_key

    data = request.data

    try:
        if 'payment_method_id' in data:
            # Create the PaymentIntent
            intent = stripe.PaymentIntent.create(
                payment_method=data['payment_method_id'],
                amount=1099,
                currency='chf',
                confirmation_method='manual',
                confirm=True,
            )
        elif 'payment_intent_id' in data:
            intent = stripe.PaymentIntent.confirm(data['payment_intent_id'])
    except stripe.error.CardError as e:
        # Display error on client
        return JsonResponse({'error': e.user_message})

    if intent.status == 'requires_action' and intent.next_action.type == 'use_stripe_sdk':
        # Tell the client to handle the action
        return JsonResponse({
            'requires_action': True,
            'payment_intent_client_secret': intent.client_secret})
    elif intent.status == 'succeeded':
        # The payment didn’t need any additional actions and completed!
        # Handle post-payment fulfillment
        return JsonResponse({'success': True})
    else:
        # Invalid status
        return JsonResponse({'error': 'Invalid PaymentIntent status'}, status=500)
