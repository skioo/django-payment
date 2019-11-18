from django.conf.urls import url
from django.contrib import admin
from django.forms import forms
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djmoney.forms import MoneyField
from import_export.admin import ExportMixin
from import_export.formats import base_formats
from moneyed.localization import format_money

from .export import PaymentResource
from .models import Payment, Transaction
from .utils import gateway_refund, gateway_void, gateway_capture


##############################################################
# Shared utilities


def amount(obj):
    return format_money(obj.amount)


amount.admin_order_field = 'amount'  # type: ignore
amount.short_description = _('amount')  # type: ignore


def created_on(obj):
    return obj.created.date()


created_on.admin_order_field = 'created'  # type: ignore
created_on.short_description = _('created')  # type: ignore


def modified_on(obj):
    return obj.modified.date()


modified_on.admin_order_field = 'modified'  # type: ignore
modified_on.short_description = _('modified')  # type: ignore


##############################################################
# Transactions
#

class TransactionInline(admin.TabularInline):
    model = Transaction
    ordering = ['-created']
    show_change_link = True

    # The gateway response is a huge field so we don't show it in the inline.
    # We let the user click on the inline change link to see all the details of the transaction.
    fields = readonly_fields = ['created', 'token', 'kind', amount, 'is_success', 'error']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    date_hierarchy = 'created'
    ordering = ['-created']
    list_filter = ['kind', 'is_success']
    list_display = ['created', amount, 'kind', 'is_success', 'token', 'error']
    search_fields = ['token', 'payment__id']

    readonly_fields = ['created']


##############################################################
# Payments

class CapturePaymentForm(forms.Form):
    amount = MoneyField(min_value=0)


def capture_payment_form(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)
    if request.method == 'POST':
        form = CapturePaymentForm(request.POST)
        if form.is_valid():
            gateway_capture(payment=payment, amount=form.cleaned_data['amount'])
            # As confirmation we take the user to the payment page
            return HttpResponseRedirect(reverse('admin:payment_payment_change', args=[payment_id]))
    else:
        form = CapturePaymentForm(initial={'amount': payment.get_charge_amount()})

    return render(
        request,
        'admin/payment/form.html',
        {
            'title': 'Capture in {}, for payment with total: {}'.format(payment.gateway, payment.total),
            'form': form,
            'opts': Payment._meta,  # Used to setup the navigation / breadcrumbs of the page
        }
    )


class RefundPaymentForm(forms.Form):
    amount = MoneyField(min_value=0)


def refund_payment_form(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)
    if request.method == 'POST':
        form = RefundPaymentForm(request.POST)
        if form.is_valid():
            gateway_refund(payment=payment, amount=form.cleaned_data['amount'])
            # As confirmation we take the user to the payment page
            return HttpResponseRedirect(reverse('admin:payment_payment_change', args=[payment_id]))
    else:
        form = RefundPaymentForm(initial={'amount': payment.captured_amount})

    return render(
        request,
        'admin/payment/form.html',
        {
            'title': 'Refund to {}, for payment with total: {}'.format(payment.gateway, payment.total),
            'form': form,
            'opts': Payment._meta,  # Used to setup the navigation / breadcrumbs of the page
        }
    )


class VoidPaymentForm(forms.Form):
    pass


def void_payment_form(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)
    if request.method == 'POST':
        form = VoidPaymentForm(request.POST)
        if form.is_valid():
            gateway_void(payment=payment)
            # As confirmation we take the user to the payment page
            return HttpResponseRedirect(reverse('admin:payment_payment_change', args=[payment_id]))
    else:
        form = VoidPaymentForm()

    return render(
        request,
        'admin/payment/form.html',
        {
            'title': 'Void in {}, for payment with total: {}'.format(payment.gateway, payment.total),
            'form': form,
            'opts': Payment._meta,  # Used to setup the navigation / breadcrumbs of the page
        }
    )


@admin.register(Payment)
class PaymentAdmin(ExportMixin, admin.ModelAdmin):
    date_hierarchy = 'created'
    ordering = ['-created']
    list_filter = ['gateway', 'is_active', 'charge_status']
    list_display = ['created', 'gateway', 'is_active', 'charge_status', 'formatted_total', 'formatted_captured_amount',
                    'customer_email']
    search_fields = ['customer_email', 'token', 'total', 'id']

    readonly_fields = ['created', 'modified', 'operation_button']
    inlines = [TransactionInline]

    resource_class = PaymentResource
    formats = (base_formats.CSV, base_formats.XLS, base_formats.JSON)  # Only useful and safe formats.

    def formatted_total(self, obj):
        return format_money(obj.total)

    formatted_total.short_description = _('total')  # type: ignore

    def formatted_captured_amount(self, obj):
        if obj.captured_amount is not None:
            return format_money(obj.captured_amount)

    formatted_captured_amount.short_description = _('captured amount')  # type: ignore

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            url(r'^(?P<payment_id>[0-9a-f-]+)/refund/$',
                self.admin_site.admin_view(refund_payment_form),
                name='payment_refund'),
            url(r'^(?P<payment_id>[0-9a-f-]+)/void/$',
                self.admin_site.admin_view(void_payment_form),
                name='payment_void'),
            url(r'^(?P<payment_id>[0-9a-f-]+)/capture/$',
                self.admin_site.admin_view(capture_payment_form),
                name='payment_capture'),
        ]
        return my_urls + urls

    def operation_button(self, payment):
        buttons = []
        if payment.can_capture():
            buttons.append(format_html(
                '<a class="button" href="{}">{}</a>',
                reverse('admin:payment_capture', args=[payment.pk]),
                _('Capture')))
        if payment.can_refund():
            buttons.append(format_html(
                '<a class="button" href="{}">{}</a>',
                reverse('admin:payment_refund', args=[payment.pk]),
                _('Refund')))
        if payment.can_void():
            buttons.append(format_html(
                '<a class="button" href="{}">{}</a>',
                reverse('admin:payment_void', args=[payment.pk]),
                _('Void')))

        return mark_safe('&nbsp;&nbsp;'.join(buttons)) if buttons else '-'

    operation_button.short_description = _('Operation')  # type: ignore
