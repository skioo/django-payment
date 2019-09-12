from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from structlog import get_logger

from payment.models import Payment
from payment.utils import gateway_capture

logger = get_logger()


def view_payment(request: HttpRequest, payment_id: int) -> HttpResponse:
    payment = get_object_or_404(Payment, id=payment_id)
    return TemplateResponse(request, 'operation_list.html', {'payment': payment})


def capture(request: HttpRequest, payment_id: int) -> HttpResponse:
    payment = get_object_or_404(Payment, id=payment_id)
    capture_result = gateway_capture(payment=payment)
    logger.info('capture', payment=payment, capture_result=capture_result)
    return redirect('view_payment', payment_id=payment_id)
