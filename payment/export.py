from import_export import resources
from import_export.fields import Field

from .models import Payment


class PaymentResource(resources.ModelResource):
    """We mostly separate amounts and currencies to make further data processing easier."""
    total_amount = Field()
    total_currency = Field()

    captured_amount = Field()
    captured_currency = Field()

    active = Field('is_active')

    class Meta:
        model = Payment
        fields = ['created', 'gateway', 'customer_email', 'charge_status', 'extra_data']
        export_order = ['created', 'active', 'customer_email', 'total_amount', 'total_currency', 'captured_amount',
                        'captured_currency', 'charge_status', 'gateway', 'extra_data']

    def dehydrate_total_amount(self, payment):
        return payment.total.amount

    def dehydrate_total_currency(self, payment):
        return payment.total.currency.code

    def dehydrate_captured_amount(self, payment):
        return payment.captured_amount.amount

    def dehydrate_captured_currency(self, payment):
        return payment.captured_amount.currency.code
