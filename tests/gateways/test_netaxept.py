# flake8: noqa
from dataclasses import dataclass, asdict
from decimal import Decimal
from unittest.mock import patch

import pytest
from moneyed import Money
from pytest import raises

from payment import GatewayConfig, ChargeStatus, TransactionKind
from payment.gateways.netaxept import gateway_to_netaxept_config, capture, refund, void, authorize
from payment.gateways.netaxept.netaxept_protocol import NetaxeptConfig, get_payment_terminal_url, \
    _iso6391_to_netaxept_language, _money_to_netaxept_amount, _money_to_netaxept_currency, register, RegisterResponse, \
    NetaxeptProtocolError, process, ProcessResponse, NetaxeptOperation, query, QueryResponse
from payment.interface import GatewayResponse
from payment.utils import create_payment_information

_gateway_config = GatewayConfig(
    auto_capture=True,
    template_path="template.html",
    connection_params={
        'merchant_id': '123456',
        'secret': 'supersekret',
        'base_url': 'https://test.epayment.nets.eu',
        'after_terminal_url': 'http://localhost',
    },
)

_netaxept_config = NetaxeptConfig(
    merchant_id='123456',
    secret='supersekret',
    base_url='https://test.epayment.nets.eu',
    after_terminal_url='http://localhost')


##############################################################################
# Utility tests

def it_should_return_netaxept_language():
    assert _iso6391_to_netaxept_language('fr') == 'fr_FR'


def it_should_return_none_netaxept_language_when_given_none():
    assert _iso6391_to_netaxept_language(None) is None


def it_should_transform_money_to_netaxept_representation():
    money = Money(10, 'NOK')
    assert _money_to_netaxept_amount(money) == 1000
    assert _money_to_netaxept_currency(money) == 'NOK'


def it_should_build_terminal_url():
    assert get_payment_terminal_url(_netaxept_config, transaction_id='11111') == \
           'https://test.epayment.nets.eu/Terminal/default.aspx?merchantId=123456&transactionId=11111'


##############################################################################
# Protocol tests

@dataclass
class MockResponse:
    status_code: int
    url: str
    encoding: str
    reason: str
    text: str


@patch('requests.post')
def it_should_register(requests_post):
    mock_response = MockResponse(
        status_code=200,
        url='https://test.epayment.nets.eu/Netaxept/Register.aspx',
        encoding='ISO-8859-1',
        reason='OK',
        text="""<?xml version="1.0" encoding="utf-8"?>
        <RegisterResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
           <TransactionId>7624b99699f344e3b6da9884d20f0b27</TransactionId>
         </RegisterResponse>""")
    requests_post.return_value = mock_response
    register_response = register(config=_netaxept_config, amount=Money(10, 'CHF'), order_number='123',
                                 customer_email='nwolff@gmail.com')
    assert register_response == RegisterResponse(
        transaction_id='7624b99699f344e3b6da9884d20f0b27',
        raw_response=asdict(mock_response))
    requests_post.assert_called_once_with(
        url='https://test.epayment.nets.eu/Netaxept/Register.aspx',
        data={'merchantId': '123456', 'token': 'supersekret', 'description': None, 'orderNumber': '123',
              'amount': 1000, 'currencyCode': 'CHF', 'autoAuth': True, 'terminalSinglePage': True,
              'language': None, 'customerEmail': 'nwolff@gmail.com', 'redirectUrl': 'http://localhost'})


@patch('requests.post')
def it_should_handle_registration_failure(requests_post):
    mock_response = MockResponse(
        status_code=200,
        url='https://test.epayment.nets.eu/Netaxept/Register.aspx',
        encoding='ISO-8859-1',
        reason='OK',
        text="""<?xml version="1.0" encoding="utf-8"?>
        <Exception xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
          <Error xsi:type="GenericError">
            <Message>Unable to translate supermerchant to submerchant, please check currency code and merchant ID</Message>
          </Error>
        </Exception>""")
    requests_post.return_value = mock_response
    with raises(NetaxeptProtocolError) as excinfo:
        register(_netaxept_config, amount=Money(10, 'CAD'), order_number='123')
        assert excinfo.value == NetaxeptProtocolError(
            error='Unable to translate supermerchant to submerchant, please check currency code and merchant ID',
            raw_response=asdict(mock_response))
    requests_post.assert_called_once_with(
        url='https://test.epayment.nets.eu/Netaxept/Register.aspx',
        data={'merchantId': '123456', 'token': 'supersekret', 'description': None, 'orderNumber': '123',
              'amount': 1000, 'currencyCode': 'CAD', 'autoAuth': True, 'terminalSinglePage': True,
              'language': None, 'redirectUrl': 'http://localhost'})


@patch('requests.post')
def it_should_process(requests_post):
    mock_response = MockResponse(
        status_code=200,
        url='https://test.epayment.nets.eu/Netaxept/Register.aspx',
        encoding='ISO-8859-1',
        reason='OK',
        text="""<?xml version="1.0" encoding="utf-8"?>
        <ProcessResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
          <BatchNumber>675</BatchNumber>
          <ExecutionTime>2019-09-16T17:31:00.7593672+02:00</ExecutionTime>
          <MerchantId>123456</MerchantId>
          <Operation>CAPTURE</Operation>
          <ResponseCode>OK</ResponseCode>
          <TransactionId>1111111111114cf693a1cf86123e0d8f</TransactionId>
          </ProcessResponse>""")
    requests_post.return_value = mock_response
    process_response = process(
        config=_netaxept_config,
        transaction_id='1111111111114cf693a1cf86123e0d8f',
        operation=NetaxeptOperation.CAPTURE,
        amount=Decimal(10))
    assert process_response == ProcessResponse(
        response_code='OK',
        raw_response=asdict(mock_response))
    requests_post.assert_called_once_with(
        url='https://test.epayment.nets.eu/Netaxept/Process.aspx',
        data={'merchantId': '123456', 'token': 'supersekret', 'operation': 'CAPTURE',
              'transactionId': '1111111111114cf693a1cf86123e0d8f', 'transactionAmount': 1000})


@patch('requests.post')
def it_should_handle_process_failure(requests_post):
    mock_response = MockResponse(
        status_code=200,
        url='https://test.epayment.nets.eu/Netaxept/Register.aspx',
        encoding='ISO-8859-1',
        reason='OK',
        text="""<?xml version="1.0" encoding="utf-8"?>
        <Exception xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
          <Error xsi:type="GenericError">
            <Message>Unable to translate supermerchant to submerchant, please check currency code and merchant ID</Message>
          </Error>
        </Exception>""")
    requests_post.return_value = mock_response
    with raises(NetaxeptProtocolError) as excinfo:
        process(
            config=_netaxept_config,
            transaction_id='1111111111114cf693a1cf86123e0d8f',
            operation=NetaxeptOperation.CAPTURE,
            amount=Decimal(10))
        assert excinfo.value == NetaxeptProtocolError(
            error='Unable to translate supermerchant to submerchant, please check currency code and merchant ID',
            raw_response=asdict(mock_response))
    requests_post.assert_called_once_with(
        url='https://test.epayment.nets.eu/Netaxept/Process.aspx',
        data={'merchantId': '123456', 'token': 'supersekret', 'operation': 'CAPTURE',
              'transactionId': '1111111111114cf693a1cf86123e0d8f', 'transactionAmount': 1000})


@patch('requests.post')
def it_should_query(requests_post):
    mock_response = MockResponse(
        status_code=200,
        url='https://test.epayment.nets.eu/Netaxept/Query.aspx',
        encoding='ISO-8859-1',
        reason='OK',
        text="""<?xml version="1.0" encoding="utf-8"?>
       <PaymentInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
         <MerchantId>11111111</MerchantId>
         <QueryFinished>2019-10-14T10:15:07.2677951+02:00</QueryFinished>
         <TransactionId>1111111111114cf693a1cf86123e0d8f</TransactionId>
         <OrderInformation>
            <Amount>700</Amount>
            <Currency>NOK</Currency>
            <OrderNumber>7</OrderNumber>
            <OrderDescription> </OrderDescription>
            <Fee>0</Fee>
            <RoundingAmount>0</RoundingAmount>
            <Total>700</Total>
            <Timestamp>2019-09-11T16:30:06.967</Timestamp>
        </OrderInformation>
        <TerminalInformation>
            <CustomerEntered>2019-09-11T16:30:08.513</CustomerEntered>
            <CustomerRedirected>2019-09-11T16:30:24.903</CustomerRedirected>
            <Browser>Chrome-Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.75 Safari/537.36</Browser>
        </TerminalInformation>
        <CustomerInformation>
            <Email />
            <IP>85.218.56.162</IP>
            <PhoneNumber /> 
            <CustomerNumber /> 
            <FirstName /> 
            <LastName /> 
            <Address1 />   
            <Address2 />  
            <Postcode />   
            <Town />  
            <Country />   
            <SocialSecurityNumber /> 
            <CompanyName />   
            <CompanyRegistrationNumber />  
        </CustomerInformation>  
        <Summary>
            <AmountCaptured>700</AmountCaptured>
            <AmountCredited>0</AmountCredited>
            <Annulled>false</Annulled>
            <Annuled>false</Annuled>
            <Authorized>true</Authorized>
            <AuthorizationId>169337</AuthorizationId>
        </Summary> 
        <CardInformation>
            <Issuer>Visa</Issuer>
            <IssuerCountry>NO</IssuerCountry>
            <MaskedPAN>492500******0004</MaskedPAN>
            <PaymentMethod>Visa</PaymentMethod>
            <ExpiryDate>2301</ExpiryDate>
            <IssuerId>3</IssuerId>
         </CardInformation>
         <History>
            <TransactionLogLine>
                <DateTime>2019-09-11T16:30:06.967</DateTime>
                <Operation>Register</Operation>
            </TransactionLogLine>
            <TransactionLogLine>
                <DateTime>2019-09-11T16:30:24.81</DateTime>
                <Description>127.0.0.1: Auto AUTH</Description>
                <Operation>Auth</Operation>
                <BatchNumber>672</BatchNumber>
            </TransactionLogLine>
         </History>
         <ErrorLog />
         <AuthenticationInformation />
         <AvtaleGiroInformation />
         <SecurityInformation>
            <CustomerIPCountry>CH</CustomerIPCountry>
            <IPCountryMatchesIssuingCountry>false</IPCountryMatchesIssuingCountry>
         </SecurityInformation>
       </PaymentInfo>""")
    requests_post.return_value = mock_response
    query_response = query(config=_netaxept_config, transaction_id='233abb21f18b47dc98469fb9000b1f21')
    assert query_response == QueryResponse(
        annulled=False,
        authorized=True,
        authorization_id='169337',
        raw_response=asdict(mock_response))


@patch('requests.post')
def it_should_handle_query_response_without_authorization_id(requests_post):
    mock_response = MockResponse(
        status_code=200,
        url='https://test.epayment.nets.eu/Netaxept/Query.aspx',
        encoding='ISO-8859-1',
        reason='OK',
        text="""<?xml version="1.0" encoding="utf-8"?>
       <PaymentInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
         <MerchantId>11111111</MerchantId>
         <QueryFinished>2019-10-14T10:15:07.2677951+02:00</QueryFinished>
         <TransactionId>1111111111114cf693a1cf86123e0d8f</TransactionId>
         <OrderInformation>
            <Amount>700</Amount>
            <Currency>NOK</Currency>
            <OrderNumber>7</OrderNumber>
            <OrderDescription> </OrderDescription>
            <Fee>0</Fee>
            <RoundingAmount>0</RoundingAmount>
            <Total>700</Total>
            <Timestamp>2019-09-11T16:30:06.967</Timestamp>
        </OrderInformation>
        <TerminalInformation>
            <CustomerEntered>2019-09-11T16:30:08.513</CustomerEntered>
            <CustomerRedirected>2019-09-11T16:30:24.903</CustomerRedirected>
            <Browser>Chrome-Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.75 Safari/537.36</Browser>
        </TerminalInformation>
        <CustomerInformation>
            <Email />
            <IP>85.218.56.162</IP>
            <PhoneNumber /> 
            <CustomerNumber /> 
            <FirstName /> 
            <LastName /> 
            <Address1 />   
            <Address2 />  
            <Postcode />   
            <Town />  
            <Country />   
            <SocialSecurityNumber /> 
            <CompanyName />   
            <CompanyRegistrationNumber />  
        </CustomerInformation>  
        <Summary>
            <AmountCaptured>700</AmountCaptured>
            <AmountCredited>0</AmountCredited>
            <Annulled>false</Annulled>
            <Annuled>false</Annuled>
            <Authorized>true</Authorized>
        </Summary> 
        <CardInformation>
            <Issuer>Visa</Issuer>
            <IssuerCountry>NO</IssuerCountry>
            <MaskedPAN>492500******0004</MaskedPAN>
            <PaymentMethod>Visa</PaymentMethod>
            <ExpiryDate>2301</ExpiryDate>
            <IssuerId>3</IssuerId>
         </CardInformation>
         <History>
            <TransactionLogLine>
                <DateTime>2019-09-11T16:30:06.967</DateTime>
                <Operation>Register</Operation>
            </TransactionLogLine>
            <TransactionLogLine>
                <DateTime>2019-09-11T16:30:24.81</DateTime>
                <Description>127.0.0.1: Auto AUTH</Description>
                <Operation>Auth</Operation>
                <BatchNumber>672</BatchNumber>
            </TransactionLogLine>
         </History>
         <ErrorLog>
            <PaymentError>
                <DateTime>2019-11-03T09:34:40.18</DateTime>
                <Operation>Auth</Operation>
                <ResponseCode>99</ResponseCode>
                <ResponseSource>Netaxept</ResponseSource>
                <ResponseText>Auth Reg Comp Failure) </ResponseText>
            </PaymentError>
         </ErrorLog>
         <AuthenticationInformation />
         <AvtaleGiroInformation />
         <SecurityInformation>
            <CustomerIPCountry>CH</CustomerIPCountry>
            <IPCountryMatchesIssuingCountry>false</IPCountryMatchesIssuingCountry>
         </SecurityInformation>
       </PaymentInfo>""")
    requests_post.return_value = mock_response
    query_response = query(config=_netaxept_config, transaction_id='233abb21f18b47dc98469fb9000b1f21')
    assert query_response == QueryResponse(
        annulled=False,
        authorized=True,
        authorization_id=None,
        raw_response=asdict(mock_response))


##############################################################################
# SPI tests

@pytest.fixture()
def netaxept_payment(payment_dummy):
    payment_dummy.charge_status = ChargeStatus.NOT_CHARGED
    payment_dummy.save()
    return payment_dummy


def it_should_build_netaxept_config():
    assert gateway_to_netaxept_config(_gateway_config) == _netaxept_config


@patch('payment.gateways.netaxept.netaxept_protocol.query')
def it_should_authorize(query, netaxept_payment):
    mock_query_response = QueryResponse(
        annulled=False,
        authorized=True,
        authorization_id=None,
        raw_response={'status_code': 200, 'url': 'https://test.epayment.nets.eu/Netaxept/Query.aspx',
                      'encoding': 'ISO-8859-1', 'reason': 'OK', 'text': 'some xml'})
    query.return_value = mock_query_response

    payment_info = create_payment_information(
        payment=netaxept_payment,
        payment_token='1111111111114cf693a1cf86123e0d8f',
        amount=Money(10, 'CHF'))

    authorize_result = authorize(config=_gateway_config, payment_information=payment_info)
    assert authorize_result == GatewayResponse(
        is_success=True,
        kind=TransactionKind.AUTH,
        amount=Decimal('10'),
        currency='CHF',
        transaction_id='1111111111114cf693a1cf86123e0d8f',
        error=None,
        raw_response=mock_query_response.raw_response)
    query.assert_called_once_with(
        config=_netaxept_config,
        transaction_id='1111111111114cf693a1cf86123e0d8f')


@patch('payment.gateways.netaxept.netaxept_protocol.query')
def it_should_not_authorize_when_query_returns_not_authorized(query, netaxept_payment):
    mock_query_response = QueryResponse(
        annulled=False,
        authorized=False,
        authorization_id=None,
        raw_response={'status_code': 200, 'url': 'https://test.epayment.nets.eu/Netaxept/Query.aspx',
                      'encoding': 'ISO-8859-1', 'reason': 'OK', 'text': 'some xml'})
    query.return_value = mock_query_response

    payment_info = create_payment_information(
        payment=netaxept_payment,
        payment_token='1111111111114cf693a1cf86123e0d8f',
        amount=Money(10, 'CHF'))

    authorize_result = authorize(config=_gateway_config, payment_information=payment_info)
    assert authorize_result == GatewayResponse(
        is_success=False,
        kind=TransactionKind.AUTH,
        amount=Decimal('10'),
        currency='CHF',
        transaction_id='1111111111114cf693a1cf86123e0d8f',
        error=None,
        raw_response=mock_query_response.raw_response)
    query.assert_called_once_with(
        config=_netaxept_config,
        transaction_id='1111111111114cf693a1cf86123e0d8f')


@patch('payment.gateways.netaxept.netaxept_protocol.process')
def it_should_capture(process, netaxept_payment):
    mock_process_response = ProcessResponse(
        response_code='OK',
        raw_response={'status_code': 200, 'url': 'https://test.epayment.nets.eu/Netaxept/Register.aspx',
                      'encoding': 'ISO-8859-1', 'reason': 'OK',
                      'text': 'some xml'})
    process.return_value = mock_process_response
    payment_info = create_payment_information(
        payment=netaxept_payment,
        payment_token='1111111111114cf693a1cf86123e0d8f',
        amount=Money(10, 'CHF'))
    capture_result = capture(config=_gateway_config, payment_information=payment_info)
    assert capture_result == GatewayResponse(
        is_success=True,
        kind=TransactionKind.CAPTURE,
        amount=Decimal('10'),
        currency='CHF',
        transaction_id='1111111111114cf693a1cf86123e0d8f',
        error=None,
        raw_response=mock_process_response.raw_response)
    process.assert_called_once_with(
        config=_netaxept_config,
        amount=Decimal('10'),
        transaction_id='1111111111114cf693a1cf86123e0d8f',
        operation=NetaxeptOperation.CAPTURE)


@patch('payment.gateways.netaxept.netaxept_protocol.process')
def it_should_not_capture_when_protocol_error(process, netaxept_payment):
    process.side_effect = NetaxeptProtocolError(error='some error', raw_response={})
    payment_info = create_payment_information(
        payment=netaxept_payment,
        payment_token='1111111111114cf693a1cf86123e0d8f',
        amount=Money(10, 'CHF'))
    capture_result = capture(config=_gateway_config, payment_information=payment_info)
    assert capture_result == GatewayResponse(
        is_success=False,
        kind=TransactionKind.CAPTURE,
        amount=Decimal('10'),
        currency='CHF',
        transaction_id='1111111111114cf693a1cf86123e0d8f',
        error='some error',
        raw_response={})
    process.assert_called_once_with(
        config=_netaxept_config,
        amount=Decimal('10'),
        transaction_id='1111111111114cf693a1cf86123e0d8f',
        operation=NetaxeptOperation.CAPTURE)


@patch('payment.gateways.netaxept.netaxept_protocol.process')
def it_should_refund(process, netaxept_payment):
    mock_process_response = ProcessResponse(
        response_code='OK',
        raw_response={
            'status_code': 200,
            'url': 'https://test.epayment.nets.eu/Netaxept/Register.aspx',
            'encoding': 'ISO-8859-1', 'reason': 'OK',
            'text': 'some xml'})
    process.return_value = mock_process_response
    payment_info = create_payment_information(
        payment=netaxept_payment,
        payment_token='1111111111114cf693a1cf86123e0d8f',
        amount=Money(10, 'CHF'))
    capture_result = refund(config=_gateway_config, payment_information=payment_info)
    assert capture_result == GatewayResponse(
        is_success=True,
        kind=TransactionKind.REFUND,
        amount=Decimal('10'),
        currency='CHF',
        transaction_id='1111111111114cf693a1cf86123e0d8f',
        error=None,
        raw_response=mock_process_response.raw_response)
    process.assert_called_once_with(
        config=_netaxept_config,
        amount=Decimal('10'),
        transaction_id='1111111111114cf693a1cf86123e0d8f',
        operation=NetaxeptOperation.CREDIT)


@patch('payment.gateways.netaxept.netaxept_protocol.process')
def it_should_void(process, netaxept_payment):
    mock_process_response = ProcessResponse(
        response_code='OK',
        raw_response={
            'status_code': 200,
            'url': 'https://test.epayment.nets.eu/Netaxept/Register.aspx',
            'encoding': 'ISO-8859-1', 'reason': 'OK',
            'text': 'some xml'})
    process.return_value = mock_process_response
    payment_info = create_payment_information(
        payment=netaxept_payment,
        payment_token='1111111111114cf693a1cf86123e0d8f',
        amount=Money(10, 'CHF'))
    void_result = void(config=_gateway_config, payment_information=payment_info)
    assert void_result == GatewayResponse(
        is_success=True,
        kind=TransactionKind.VOID,
        amount=Decimal('10'),
        currency='CHF',
        transaction_id='1111111111114cf693a1cf86123e0d8f',
        error=None,
        raw_response=mock_process_response.raw_response)
    process.assert_called_once_with(
        config=_netaxept_config,
        amount=Decimal('10'),
        transaction_id='1111111111114cf693a1cf86123e0d8f',
        operation=NetaxeptOperation.ANNUL)
