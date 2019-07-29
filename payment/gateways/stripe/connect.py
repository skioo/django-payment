from django.conf import settings
from structlog import get_logger

logger = get_logger()


def add_transfer_data(charge_payload, destination, percent):
    full_amount = charge_payload['amount']
    transfer_amount = int(full_amount * percent / 100)
    charge_payload['transfer_data'] = {
        'destination': destination,
        'amount': transfer_amount
    }
    logger.debug('stripe_connect_maybe_add_transfer_data',
                 full_amount=full_amount,
                 transfer_amount=transfer_amount,
                 destination=destination)


def maybe_add_transfer_data(charge_payload):
    if hasattr(settings, 'STRIPE_CONNECT'):
        _connect_settings = settings.STRIPE_CONNECT
        _transfer_destination = _connect_settings['transfer_destination']
        _transfer_percent_string = _connect_settings['transfer_percent']
        try:
            _transfer_percent = int(_transfer_percent_string)
        except ValueError:
            raise Exception("STRIPE_TRANSFER_PERCENT should be an int")
        if _transfer_percent < 0 or _transfer_percent > 100:
            raise Exception("STRIPE_TRANSFER_PERCENT should be between 0 and 100")
        add_transfer_data(charge_payload=charge_payload, destination=_transfer_destination, percent=_transfer_percent)
