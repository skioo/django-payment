"""
Low-level communications with netaxept.

To avoid overcustomization this library makes a few choices on behalf of the library user:
- AutoAuth is turned on.
- We always redirect after the terminal (after_terminal_url must be configured)
- The terminal is displayed as a single page.

Netaxept reference:
-------------------
https://shop.nets.eu/web/partners/home
Read this first: https://shop.nets.eu/web/partners/flow-outline
Terminal details: https://shop.nets.eu/web/partners/terminal-options
API details: https://shop.nets.eu/web/partners/appi
Test card numbers: https://shop.nets.eu/web/partners/test-cards
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional, Union, Dict, Any
from urllib.parse import urlencode, urljoin

import requests
import xmltodict
from moneyed import Money
from structlog import get_logger

logger = get_logger()


@dataclass
class NetaxeptConfig:
    merchant_id: str
    secret: str
    base_url: str
    after_terminal_url: str


class NetaxeptOperation(Enum):
    AUTH = 'AUTH'
    VERIFY = 'VERIFY'
    SALE = 'SALE'
    CAPTURE = 'CAPTURE'
    CREDIT = 'CREDIT'
    ANNUL = 'ANNUL'


class NetaxeptProtocolError(Exception):
    def __init__(self, error: str, raw_response: Dict[str, str]):
        self.error = error
        self.raw_response = raw_response


@dataclass
class RegisterResponse:
    transaction_id: str
    raw_response: Dict[str, Any]


def register(config: NetaxeptConfig, amount: Money, order_number: Union[str, int],
             language: Optional[str] = None, description: Optional[str] = None,
             customer_email: Optional[str] = None) -> RegisterResponse:
    """
    Registering a payment is the first step for netaxept, before taking the user to the netaxept
    terminal hosted page.

    See: https://shop.nets.eu/web/partners/register

    :param config: The netaxept configuration
    :param amount: The amount of the payment.
    :param order_number: An alphanumerical string identifying the payment. 32 chars max (letters and numbers)
    :param language: The iso639-1 code of the language in which the terminal should be displayed.
    :param description: A text that will be displayed in the netaxept admin (but not to the user).
    :param customer_email: The email of the customer, can then be seen in the netaxept admin portal.
    :return: a RegisterResponse
    :raises: NetaxeptProtocolError
    """

    logger.info('netaxept-register', amount=amount, order_number=order_number, language=language,
                description=description, customer_email=customer_email)

    params = {
        'merchantId': config.merchant_id,
        'token': config.secret,
        'description': description,

        # Order
        'orderNumber': order_number,
        'amount': _money_to_netaxept_amount(amount),
        'currencyCode': _money_to_netaxept_currency(amount),

        # Terminal
        'autoAuth': True,
        'terminalSinglePage': True,
        'language': _iso6391_to_netaxept_language(language),
        'redirectUrl': config.after_terminal_url
    }

    if customer_email is not None:
        params['customerEmail'] = customer_email

    response = requests.post(url=urljoin(config.base_url, 'Netaxept/Register.aspx'), data=params)
    raw_response = _build_raw_response(response)
    logger.info('netaxept-register', amount=amount, order_number=order_number, language=language,
                description=description, raw_response=raw_response)

    if response.status_code == requests.codes.ok:
        d = xmltodict.parse(response.text)
        if 'RegisterResponse' in d:
            return RegisterResponse(
                transaction_id=d['RegisterResponse']['TransactionId'],
                raw_response=raw_response)
        elif 'Exception' in d:
            raise NetaxeptProtocolError(d['Exception']['Error']['Message'], raw_response)
    raise NetaxeptProtocolError(response.reason, raw_response)


@dataclass
class ProcessResponse:
    response_code: str
    raw_response: Dict[str, Any]


def process(config: NetaxeptConfig, transaction_id: str, operation: NetaxeptOperation,
            amount: Decimal) -> ProcessResponse:
    """
    :param config: The netaxept config
    :param transaction_id: The id of the transaction, should match the transaction id of the register call
    :param operation: The type of operation to perform
    :param amount: The amount to process (only applies to Capture and Refund)
    :return: ProcessResponse
    :raises: NetaxeptProtocolError
    """
    logger.info('netaxept-process', transaction_id=transaction_id, operation=operation.value, amount=amount)

    params = {
        'merchantId': config.merchant_id,
        'token': config.secret,
        'operation': operation.value,
        'transactionId': transaction_id,
        'transactionAmount': _decimal_to_netaxept_amount(amount),
    }

    response = requests.post(url=urljoin(config.base_url, 'Netaxept/Process.aspx'), data=params)
    raw_response = _build_raw_response(response)
    logger.info('netaxept-process-response', transaction_id=transaction_id, operation=operation.value,
                amount=amount, raw_response=raw_response)

    if response.status_code == requests.codes.ok:
        d = xmltodict.parse(response.text)
        if 'ProcessResponse' in d:
            return ProcessResponse(
                response_code=d['ProcessResponse']['ResponseCode'],
                raw_response=raw_response)
        elif 'Exception' in d:
            raise NetaxeptProtocolError(d['Exception']['Error']['Message'], raw_response)
    raise NetaxeptProtocolError(response.reason, raw_response)


def get_payment_terminal_url(config: NetaxeptConfig, transaction_id: str) -> str:
    qs = urlencode({'merchantId': config.merchant_id, 'transactionId': transaction_id})
    return '{}?{}'.format(urljoin(config.base_url, 'Terminal/default.aspx'), qs)


@dataclass
class QueryResponse:
    """ The query response is a very rich, deeply nested object, but we just model what's interesting for our use-case.
    (The complete response is captured in the raw_response)
    """
    annulled: bool
    authorized: bool
    authorization_id: Optional[str]
    raw_response: Dict[str, Any]


def query(config: NetaxeptConfig, transaction_id: str) -> QueryResponse:
    logger.info('netaxept-query', transaction_id=transaction_id)

    params = {
        'merchantId': config.merchant_id,
        'token': config.secret,
        'transactionId': transaction_id,
    }

    response = requests.post(url=urljoin(config.base_url, 'Netaxept/Query.aspx'), data=params)
    raw_response = _build_raw_response(response)
    logger.info('netaxept-query-response', transaction_id=transaction_id, raw_response=raw_response)
    if response.status_code == requests.codes.ok:
        d = xmltodict.parse(response.text)
        if 'PaymentInfo' in d:
            summary = d['PaymentInfo']['Summary']
            annulled = summary['Annulled'] == 'true'
            authorized = summary['Authorized'] == 'true'
            authorization_id = summary.get('AuthorizationId')  # AuthorizationId may be absent from the response
            return QueryResponse(
                annulled=annulled,
                authorized=authorized,
                authorization_id=authorization_id,
                raw_response=raw_response
            )
        elif 'Exception' in d:
            raise NetaxeptProtocolError(d['Exception']['Error']['Message'], raw_response)
    raise NetaxeptProtocolError(response.reason, raw_response)


def _decimal_to_netaxept_amount(decimal_amount: Decimal) -> int:
    """ Return the netaxept representation of the decimal representation of the amount. """
    return int((decimal_amount * 100).to_integral_value())


def _money_to_netaxept_amount(money: Money) -> int:
    """ Return the netaxept representation of the money's amount. """
    return _decimal_to_netaxept_amount(money.amount)


def _money_to_netaxept_currency(money: Money) -> str:
    """ Return the netaxept representation of the money's currency. """
    return money.currency.code


_netaxept_language_codes = ['no_NO', 'sv_SE', 'da_DK', 'fi_FI ', 'en_GB', 'de_DE', 'fr_FR', 'ru_RU ', 'pl_PL',
                            'nl_NL', 'es_ES', 'it_IT', 'pt_PT', 'et_EE', 'lv_LV', 'lt_LT']

_netaxept_language_codes_by_prefix = {l[:2]: l for l in _netaxept_language_codes}


def _iso6391_to_netaxept_language(iso6391_language: Optional[str]) -> Optional[str]:
    """ Return the netaxept representation of the language. """
    return _netaxept_language_codes_by_prefix.get(iso6391_language)  # type:ignore


def _build_raw_response(response: requests.Response):
    return {
        'status_code': response.status_code,
        'url': response.url,
        'encoding': response.encoding,
        'reason': response.reason,
        'text': response.text,
    }
