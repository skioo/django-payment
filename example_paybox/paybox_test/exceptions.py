class InvalidPaymentSolutionException(Exception):
    """
    An exceptions raised when you attempt operations not allowed
    on the payment solution in question.
    e.g calling Paybox direct plus only operations on Paybox direct methods.
    """
    def __init__(self, message, payload=None):
        self.message = message
        self.payload = payload

    def __str__(self):
        return str(self.message)


class InvalidParametersException(Exception):
    """
    An exceptions raised when Paybox has issues with parameters
    passed for the call.
    """
    def __init__(self, message, payload=None):
        self.message = message
        self.payload = payload

    def __str__(self):
        return str(self.message)


class PayboxEndpointException(Exception):
    """
    An exception raised when Paybox endpoints can't seem to be reached.
    """
    def __init__(self, message, payload=None):
        self.message = message
        self.payload = payload

    def __str__(self):
        return str(self.message)
