# django-payment

[![Build Status](https://travis-ci.org/skioo/django-payment.svg?branch=master)](https://travis-ci.org/skioo/django-payment)
[![PyPI version](https://badge.fury.io/py/django-payment.svg)](https://badge.fury.io/py/django-payment)
[![Requirements Status](https://requires.io/github/skioo/django-payment/requirements.svg?branch=master)](https://requires.io/github/skioo/django-payment/requirements/?branch=master)
[![Coverage Status](https://coveralls.io/repos/github/skioo/django-payment/badge.svg?branch=master)](https://coveralls.io/github/skioo/django-payment?branch=master)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)


## Requirements
* Python: 3.6 and over
* Django: 2.1 and over


## Usage
To use django-payments in your existing django project:

Add payment and import_export to your `INSTALLED_APPS`:

    INSTALLED_APPS = (
        ...
        'payment.apps.PaymentConfig',
        'import_export',
        ...
    )


Create the payment tables by running the migrations: 

    ./manage.py migrate


Add payment urls to your urlpatterns: 

    urlpatterns = [
        ...
        path('payment/', include('payment.urls')),
        ...
     ]


Configure the CHECKOUT_PAYMENT_GATEWAYS and PAYMENT_GATEWAYS settings. See [example settings.py](example_project/settings.py)


## Payment gateways
This module provides implementations for the following payment-gateways:

### Stripe 
- Authorization
- Capture
- Refund
- Split Payment with stripe connect
- Adding metadata to the stripe payment, for easy sorting in stripe

[More Stripe information](docs/stripe.md)

### Netaxept
Implemented features:
- Authorization
- Capture
- Refund

[More Netaxept information](docs/netaxept.md)

## The example project
The source distribution includes an example project that lets one exercise 
the different gateway implementations without having to write any code.

Install the django-payment dependencies (the example project has identical dependencies):

    pip install -e . 
    
 Create the database and admin user:

    cd example_project
    ./manage.py migrate
    ./manage.py createsuperuser
    
 Start the dev server:
 
    ./manage.py runserver

Then point your browser to:

    http://127.0.0.1:8000/admin/
    
Create a new payment (make sure the captured amount currency is the same as the total currency)

Then operate on that payment with:

    http://127.0.0.1:8000/payment/<payment-id>

## Development

To install all dependencies:

    pip install -e .
    
To run unit tests:

    pip install pytest-django
    pytest

To lint, typecheck, test on all supported versions of python and django.
Also to verify you didn't forget to create a migration:

    pip install tox
    tox

To install the version being developed into another django project:

    pip install -e <path-to-this-directory>


More information about [the design of this application](docs/design.md)
