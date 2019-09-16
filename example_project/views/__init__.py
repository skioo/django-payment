from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from structlog import get_logger

from payment.models import Payment

logger = get_logger()


def view_payment(request: HttpRequest, payment_id: int) -> HttpResponse:
    payment = get_object_or_404(Payment, id=payment_id)
    return TemplateResponse(request, 'operation_list.html', {'payment': payment})
