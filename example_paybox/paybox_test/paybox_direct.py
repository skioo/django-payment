import requests
from urllib import parse

from .exceptions import InvalidPaymentSolutionException, InvalidParametersException, PayboxEndpointException
import urllib.parse
from time import sleep


from django.conf import settings


class PayboxDirectTransaction:
    """A Paybox Direct transaction, from your server to Paybox server
    Attributes:
        REQUIRED   The values nedded to call for a payment
        OPTIONAL   The values you may add to modify Paybox behavior
        RESPONSE_CODES  Every response code Paybox may return after a payment attempt
        OPERATION_TYPES  Codes for every type of operation possible
        ACTIVITE  This parameter allows to inform the acquirer (bank) how the transaction was initiated and how the card entry was realized.
    """

    def __init__(self, production=False, dateq=None, operation_type=None, numquestion=None, montant=None,
                 reference=None, refabonne=None, cle=None, devise=None, porteur=None, dateval=None, cvv=None,
                 activite=None, archivage=None, differe=None, numappel=None, numtrans=None, autorisation=None,
                 pays=None, priv_codetraitement=None, datenaiss=None, acquereur=None, typecarte=None, url_encode=None,
                 sha_1=None, errorcodetest=None, id_session=None, secure_3d=False,
                 url_http_direct=None):

        self.production = production
        self.RETRY_CODES = ["00001", "00097", "00098"]
        self.card_verification_api_redirect_url = url_http_direct
        self.session_id = id_session
        self.secure_3d = secure_3d
        self.id3d = None

        self.ACTIVITE = {
            "020": "Not specified",
            "021": "Telephone order",
            "022": "Mail Order",
            "023": "Minitel(France)",
            "024": "Internet payment",
            "027": "Recurring payment"
        }

        # VERSION=00104&TYPE=00001&SITE=1999888&RANG=32&CLE=1999888I&NUM
        # QUESTION=194102418&MONTANT=1000&DEVISE=978&REFERENCE=TestPaybox&PORTEUR=1111222233334444&DATEVAL=0520&CVV=222&ACTIVITE=024&D
        # ATEQ=30012013&PAYS=

        self.REQUIRED = {
            "VERSION": "00104",  # Version of the protocol PPPS used
            "TYPE": operation_type,  # Transaction operation type
            "SITE": settings.PAYBOX_SITE,  # SITE NUMBER (given by Paybox) 7 digits
            "RANG": settings.PAYBOX_RANG,  # RANG NUMBER (given by Paybox) 2 digits
            "CLE": cle,  # password for the merchant backoffice that is provided by the technical support upon the
                         # creation of the merchant account on the Paybox platform.
            "NUMQUESTION": numquestion,  # Unique identifier for the request that allows to avoid confusion
                                             # in case of multiple simultaneous requests.
            "MONTANT": montant,  # Amount of the transaction in cents
            "DEVISE": devise if devise else "978",  # Currency code of the transaction
            "REFERENCE": reference,  # Merchant's reference number
            "PORTEUR": porteur,  # PAN (card number) of the customer, without any spaces and left aligned
            "DATEVAL": dateval,  # Expiry date of the card. (MMYY)
        }

        self.OPTIONAL = {
            "CVV": cvv,  # Visual cryptogram on the back of the card. 3 0r 4 characters
            "REFABONNE": refabonne,  # Merchant reference number allowing him to clearly identify the
                                     # subscriber (profile) that corresponds to the transaction.
            "NUMAPPEL": numappel,  # This number is returned by Verifone when a transaction is successfully processed
            "NUMTRANS": numtrans,  # This number is returned by Verifone when a transaction is successfully processed
            "ACTIVITE": activite,  # This parameter allows to inform the acquirer (bank) how the transaction
                                   # was initiated and how the card entry was realized.
            "DATEQ": dateq,  # Date and time of the request using the format DDMMYYYYHHMMSS
            "ARCHIVAGE": archivage,  # This reference is transmitted to the acquirer (bank) of the merchant during
                                     # the settlement of the transaction
            "DIFFERE": differe,  # Number of days to postpone the settlement
            "AUTORISATION": autorisation,  # Authorization number provided by the merchant that was obtained by
                                           # telephone call to the acquirer (bank)
            "PAYS": pays,  # If the parameter is present (even empty), Paybox Direct returns the country
                           # code of issuance of the card in the response
            "PRIV_CODETRAITEMENT": priv_codetraitement,  # Parameter filled in by the merchant to indicate the
                                                         # payment option that is proposed to the cardholder of a SOFINCO card
                                                         # (or partner card of SOFINCO) or COFINOGA.3 digits. payment language.
                                                         # GBR for English
            "DATENAISS": datenaiss,  # Birthday of the cardholder for the cards of COFINOGA. Date(DDMMYYYY)
            "ACQUEREUR": acquereur,  # Defines the payment method used. The possible values are
                                     # [PAYPAL, EMS, ATOSBE, BCMC, EQUENS, PSC, FINAREF, 34ONEY]
            "TYPECARTE": typecarte,  # If the parameter is present (even empty), Paybox Direct will return the type of
                                     # card in the response (for a payment using with a card).
            "URL_ENCODE": url_encode,  # If the parameter contains O, Paybox Direct will URL-decode the value provided
                                       # in each field before evaluating them.
            "SHA-1": sha_1,  # If the parameter is present (even empty), Paybox Direct will return the hash of the
                                 # card in the response (for a payment with a card).
            "ERRORCODETEST": errorcodetest,  # The error code to return (forced) while doing integration testing in
                                             # the pre-production environment. In production the parameter is not
                                             # taken into account.
            "ID3D": self.id3d,  # Context identifier Verifone that holds the authentication result of the MPI
        }

        self.RESPONSE_CODES = {
            "00000": "Operation successful",
            "00001": "Connection failed.",
            "001xx": "Payment rejected",
            "00002": "Error due to incoherence",
            "00003": "Internal paybox error.",
            "00004": "Card number invalid",
            "00005": "Request number invalid",
            "00006": "Site or rang invalid. Connection rejected",
            "00007": "Date invalid",
            "00008": "Card expiration date invalid",
            "00009": "Requested operation invalid",
            "00010": "Unrecognized currency",
            "00011": "Incorrect amount",
            "00012": "Order reference invalid",
            "00013": "This version is no longer supported",
            "00014": "Received request incoherent",
            "00015": "Error accessing data previously referenced",
            "00016": "Subscriber already exists",
            "00017": "Subscriber does not exist",
            "00018": "Transaction was not found",
            "00019": "Reserved",
            "00020": "Visual cryptogram missing(CVV)",
            "00021": "Card not authorized",
            "00022": "Threshold reached",
            "00023": "Cardholder already seen",
            "00024": "Country code filtered",
            "00026": "Activity code incorrect",
            "00040": "Card holder enrolled but not authenticated",
            "00097": "Connection timeout",
            "00098": "Internal connection timeout",
            "00099": "Incoherence between query and reply",
        }

        self.OPERATION_TYPES = {
            "00001": "Authorization Only",
            "00002": "Debit(Capture)",
            "00003": "Authorization + Capture",
            "00004": "Credit",
            "00005": "Cancel",
            "00011": "Check if a transaction exists",
            "00012": "Transaction without authorization request",
            "00014": "Refund",
            "00017": "Inquiry"
        }

        self.DIRECT_PLUS_ONLY_OPERATIONS = [
            "00051", "00052", "00053", "00054", "00055", "00056", "00057", "00058", "00061"
        ]

        self.DELAY_OPERATIONS = [
            "00051", "00053"
        ]

    def action_url(self):
        if self.production:
            main_url = "https://ppps.paybox.com/PPPS.php"
            backup_url = "https://ppps1.paybox.com/PPPS.php"
            request = requests.get(main_url)
            if request.status_code == 200:
                return main_url
            else:
                request = requests.get(backup_url)
                if request.status_code == 200:
                    return backup_url
        else:
            main_url = "https://preprod-ppps.paybox.com/PPPS.php"
            return main_url
        raise PayboxEndpointException(message="Paybox Direct URL and its backup not responsive.")

    def remote_mpi_url(self):
        if self.production:
            mpi_url1 = "https://tpeweb.paybox.com/cgi/RemoteMPI.cgi"
            mpi_url2 = "https://tpeweb1.paybox.com/cgi/RemoteMPI.cgi"
            mpi_url3 = "https://tpeweb1.paybox.com/cgi/RemoteMPI.cgi"
            mpi_url4 = "https://tpeweb0.paybox.com/cgi/RemoteMPI.cgi"
            request = requests.get(mpi_url1)
            if request.status_code == 200:
                return mpi_url1
            else:
                request = requests.get(mpi_url2)
                if request.status_code == 200:
                    return mpi_url2
                else:
                    request = requests.get(mpi_url3)
                    if request.status_code == 200:
                        return mpi_url3
                    else:
                        request = requests.get(mpi_url4)
                        if request.status_code == 200:
                            return mpi_url4
        else:
            remote_mpi_url = "https://preprod-tpeweb.paybox.com/cgi/RemoteMPI.cgi"
            return remote_mpi_url
        raise PayboxEndpointException(message="Paybox MPI URL is not responsive.")

    def remote_mpi_authenticate(self, session_id):
        """
        To carry out a 3D-Secure transaction, merchants will need to authenticate the cardholder before
        calling Paybox Direct Applications
        :return: {"ID3D": "", "StatusPBX": "", "Check": "", "IdSession": "", "3DCAVV": "",
                 "3DCAVVALGO": "", "3DECI": "", "3DENROLLED": "", "3DERROR": "", "3DSIGNVAL": "",
                 "3DSTATUS": "", "3DXID": "", "Check": ""}
        """
        card_verification_string = "IdMerchant={0},IdSession={1},Amount={2},Currency={3},CCNumber={4},CCExpDate={5},CVVCode={6},URLHttpDirect={7}".format(settings.PAYBOX_IDENTIFIANT, session_id, self.REQUIRED['MONTANT'], self.REQUIRED['DEVISE'], self.REQUIRED['PORTEUR'], self.REQUIRED['DATEVAL'],  self.OPTIONAL['CVV'], self.card_verification_api_redirect_url)

        remote_mpi_call = requests.post(self.remote_mpi_url(), data=card_verification_string)
        response = dict(parse.parse_qsl(remote_mpi_call.text))
        try:
            if urllib.parse.unquote(response['StatusPBX']) == "Autorisation à faire":
                self.id3d = response['ID3D']
            elif urllib.parse.unquote(response['StatusPBX']) == "Autorisation à ne pas faire":
                raise InvalidParametersException("Cardholder authentication failed.")
        except KeyError:
            raise InvalidParametersException(message="3D secure authentication failed.")
        return response

    def post_to_paybox(self, numquestion, operation_type=None):
        """
        To carry out a 3D-Secure transaction, merchants will need to authenticate the cardholder before
        calling Paybox Direct Applications
        :return: {"CODEREPONSE”": "", "COMMENTAIRE": "", "AUTORISATION": "", "NUMAPPEL": ""
                  "NUMQUESTION": "", "NUMTRANS": "", "PAYS": "", "PORTEUR": "", "RANG": "",
                  "REFABONNE": "", "REMISE": "", "SHA-1": "", "SITE": "", "STATUS": "",
                  "TYPECARTE": ""}
        """
        self.REQUIRED['TYPE'] = operation_type
        if self.secure_3d:
            if self.id3d is None:
                raise InvalidParametersException(message="3D Secure payments require mpi authentication.")
        if operation_type in self.DIRECT_PLUS_ONLY_OPERATIONS:
            raise InvalidPaymentSolutionException(
                message="You have called a Paybox Direct Plus operation on a Paybox Direct method.")
        if operation_type in self.DELAY_OPERATIONS:
            sleep(1)
        self.REQUIRED['NUMQUESTION'] = numquestion
        payload = {**self.REQUIRED, **self.OPTIONAL}
        session = requests.Session()
        paybox_call = session.post(self.action_url(), data=payload)
        response = dict(parse.parse_qsl(paybox_call.text))
        if response['CODEREPONSE'] in self.RETRY_CODES:
            self.post_to_paybox(numquestion, operation_type)
        if self.REQUIRED['TYPE'] == "00001":
            self.OPTIONAL['NUMAPPEL'] = response['NUMAPPEL']
            self.OPTIONAL['NUMTRANS'] = response['NUMTRANS']
        return response

    def construct_html_form(self):
        """
        Returns an html form ready to be POSTed to Paybox Direct (string)
        :return: str <form>
        """

        optional_fields = "\n".join(
            [
                "<input type='hidden' name='{0}' value='{1}'>".format(
                    field, self.OPTIONAL[field]
                )
                for field in self.OPTIONAL
                if self.OPTIONAL[field]
            ]
        )

        html = """<form method=POST action="{action_url}">
            <input name = "DATEQ" value = "{required[DATEQ]}" type="text">
            <input name = "TYPE" value = "{required[TYPE]}" type="text">
            <input name = "NUMQUESTION" value = "{required[NUMQUESTION]}" type="text">
            <input name = "MONTANT" value = "{required[MONTANT]}" type="text">
            <input name = "SITE" value = "{required[SITE]}" type="text">
            <input name = "RANG" value = "{required[RANG]}" type="text">
            <input name="REFERENCE" value="{required[REFERENCE]}" type="text">
            <input name="REFABONNE" value="{required[REFABONNE]}" type="text">
            <input name="PORTEUR" value="{required[PORTEUR]}" type="text">
            <input name="DATEVAL" value="{required[DATEVAL]}" type="text">
            <input name="NUMAPPEL" value="{required[NUMAPPEL]}" type="text">
            <input name="NUMTRANS" value="{required[NUMTRANS]}" type="text">
            {optional}
            <input type="submit" value="Pay">
        </form>"""

        return html.format(
            action=self.action_url(), required=self.REQUIRED, optional=optional_fields
        )
