from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from moneyed.localization import format_money

from .models import Payment, Transaction


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

    def has_module_permission(self, request):
        # Prevent TransactionAdmin from appearing in the admin menu,
        # to view a transaction detail users should start navigation from a Payment.
        return False


##############################################################
# Payments

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    date_hierarchy = 'created'
    ordering = ['-created']
    list_filter = ['gateway', 'is_active', 'charge_status']
    list_display = ['created', 'gateway', 'is_active', 'charge_status', 'formatted_total', 'formatted_captured_amount',
                    'customer_email']
    search_fields = ['customer_email', 'token', 'total', 'id']

    inlines = [TransactionInline]

    def formatted_total(self, obj):
        return format_money(obj.total)

    formatted_total.short_description = _('total')  # type: ignore

    def formatted_captured_amount(self, obj):
        if obj.captured_amount is not None:
            return format_money(obj.captured_amount)

    formatted_captured_amount.short_description = _('captured amount')  # type: ignore
