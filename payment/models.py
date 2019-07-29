import json
from operator import attrgetter

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import CASCADE
from django.utils.translation import ugettext_lazy as _
from djmoney.models.fields import MoneyField
from moneyed import Money
from typing import Optional, Dict

from . import (
    ChargeStatus,
    CustomPaymentChoices,
    TransactionKind,
    get_payment_gateway,
)


class Payment(models.Model):
    """A model that represents a single payment.

    This might be a transactable payment information such as credit card
    details, gift card information or a customer's authorization to charge
    their PayPal account.

    All payment process related pieces of information are stored
    at the gateway level, we are operating on the reusable token
    which is a unique identifier of the customer for given gateway.

    Several payment methods can be used within a single order. Each payment
    method may consist of multiple transactions.
    """

    gateway = models.CharField(_('gateway'), max_length=255)
    is_active = models.BooleanField(_('is_active'), default=True)
    created = models.DateTimeField(_('created'), auto_now_add=True)
    modified = models.DateTimeField(_('modified'), auto_now=True)
    charge_status = models.CharField(_('charge status'), max_length=20, choices=ChargeStatus.CHOICES,
                                     default=ChargeStatus.NOT_CHARGED)
    token = models.CharField(_('token'), max_length=128, blank=True, default="")
    total = MoneyField(_('total'), max_digits=12, decimal_places=2)
    captured_amount = MoneyField(_('captured amount'), max_digits=12, decimal_places=2)

    cc_first_digits = models.CharField(_('cc first digits'), max_length=6, blank=True, default="")
    cc_last_digits = models.CharField(_('cc last digits'), max_length=4, blank=True, default="")
    cc_brand = models.CharField(_('cc brand'), max_length=40, blank=True, default="")
    cc_exp_month = models.PositiveIntegerField(_('cc exp month'),
                                               validators=[MinValueValidator(1), MaxValueValidator(12)], null=True,
                                               blank=True)
    cc_exp_year = models.PositiveIntegerField(_('cc exp year'), validators=[MinValueValidator(1000)], null=True,
                                              blank=True)

    customer_email = models.EmailField(_('customer email'), )

    customer_ip_address = models.GenericIPAddressField(_('customer ip address'), blank=True, null=True)
    extra_data = models.TextField(_('extra data'), blank=True, default="")

    class Meta:
        verbose_name = _('payment')
        verbose_name_plural = _('payments')
        ordering = ("pk",)

    def __str__(self):
        return _('Payment {} ({})').format(self.id, self.get_charge_status_display())

    def __repr__(self):
        return "Payment(gateway=%s, is_active=%s, created=%s, charge_status=%s)" % \
               (self.gateway, self.is_active, self.created, self.charge_status)

    def clean(self):
        if self.captured_amount is None:
            self.captured_amount = Money(0, self.total.currency)

    def get_last_transaction(self):
        return max(self.transactions.all(), default=None, key=attrgetter("pk"))

    def get_authorized_amount(self):
        money = Money(0, self.total.currency)

        # Query all the transactions which should be prefetched
        # to optimize db queries
        transactions = self.transactions.all()

        # There is no authorized amount anymore when capture is succeeded
        # since capture can only be made once, even it is a partial capture
        if any([txn.kind == TransactionKind.CAPTURE and txn.is_success for txn in transactions]):
            return money

        # Filter the succeeded auth transactions
        authorized_txns = [txn for txn in transactions if txn.kind == TransactionKind.AUTH and txn.is_success]

        for txn in authorized_txns:
            money += txn.amount

        # If multiple partial capture is supported later though it's unlikely,
        # the authorized amount should exclude the already captured amount here
        return money

    def get_charge_amount(self):
        """Retrieve the maximum capture possible."""
        return self.total - self.captured_amount

    @property
    def is_authorized(self):
        return any([txn.kind == TransactionKind.AUTH and txn.is_success for txn in self.transactions.all()])

    @property
    def not_charged(self):
        return self.charge_status == ChargeStatus.NOT_CHARGED

    def can_authorize(self):
        return self.is_active and self.not_charged

    def can_capture(self):
        if not (self.is_active and self.not_charged):
            return False

        _, gateway_config = get_payment_gateway(self.gateway)
        if gateway_config.auto_capture:
            return self.is_authorized

        return True

    def can_void(self):
        return self.is_active and self.not_charged and self.is_authorized

    def can_refund(self):
        can_refund_charge_status = (
            ChargeStatus.PARTIALLY_CHARGED,
            ChargeStatus.FULLY_CHARGED,
            ChargeStatus.PARTIALLY_REFUNDED,
        )
        return (
                self.is_active
                and self.charge_status in can_refund_charge_status
                and self.gateway != CustomPaymentChoices.MANUAL
        )

    @property
    def metadata(self) -> Dict[str, str]:
        if self.extra_data == '':
            return {}
        else:
            return json.loads(self.extra_data)

    @metadata.setter
    def metadata(self, d: Optional[Dict[str, str]]):
        if d == {}:
            self.extra_data = ''
        else:  # Could so some assertions on the types of keys and values
            self.extra_data = json.dumps(d)


class Transaction(models.Model):
    """Represents a single payment operation.

    Transaction is an attempt to transfer money between your store
    and your customers, with a chosen payment method.
    """

    created = models.DateTimeField(_('created'), auto_now_add=True, editable=False)
    payment = models.ForeignKey(Payment, related_name="transactions", on_delete=CASCADE,
                                verbose_name=_('payment'))
    token = models.CharField(_('token'), max_length=128, blank=True, default="")
    kind = models.CharField(_('kind'), max_length=10, choices=TransactionKind.CHOICES)
    is_success = models.BooleanField(_('is success'), default=False)
    amount = MoneyField(_('amount'), max_digits=12, decimal_places=2)
    error = models.CharField(_('error'), max_length=256, blank=True, null=True)
    gateway_response = models.TextField(_('gateway response'), )  # JSON or XML

    class Meta:
        verbose_name = _('transaction')
        verbose_name_plural = _('transactions')
        ordering = ("pk",)

    def __repr__(self):
        return "Transaction(type=%s, is_success=%s, created=%s)" % \
               (self.kind, self.is_success, self.created)
