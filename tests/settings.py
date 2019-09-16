# flake8: noqa

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'test.db'
    },
}

SECRET_KEY = 'not_so_secret'

USE_TZ = True

# Use a fast hasher to speed up tests.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.messages',
    'django.contrib.contenttypes',
    'djmoney',
    'payment.apps.PaymentConfig',
]

MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

STATIC_URL = '/static/'

ROOT_URLCONF = 'tests.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.request',
                'django.template.context_processors.static',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DUMMY = 'dummy'
STRIPE = 'stripe'
NETAXEPT = 'netaxept'

CHECKOUT_PAYMENT_GATEWAYS = {
    DUMMY: 'Dummy gateway',
    STRIPE: 'Stripe',
    NETAXEPT: 'Netaxept',
}

PAYMENT_GATEWAYS = {
    DUMMY: {
        'module': 'payment.gateways.dummy',
        'config': {
            'auto_capture': True,
            'connection_params': {},
            'template_path': 'payment/dummy.html',
        }
    },
    STRIPE: {
        'module': 'payment.gateways.stripe',
        'config': {
            'auto_capture': True,
            'template_path': 'payment/stripe.html',
            'connection_params': {
                'public_key': os.environ.get('STRIPE_PUBLIC_KEY'),
                'secret_key': os.environ.get('STRIPE_SECRET_KEY'),
                'store_name': os.environ.get('STRIPE_STORE_NAME', 'skioo shop'),
                'store_image': os.environ.get('STRIPE_STORE_IMAGE', None),
                'prefill': os.environ.get('STRIPE_PREFILL', True),
                'remember_me': os.environ.get('STRIPE_REMEMBER_ME', False),
                'locale': os.environ.get('STRIPE_LOCALE', 'auto'),
                'enable_billing_address': os.environ.get('STRIPE_ENABLE_BILLING_ADDRESS', False),
                'enable_shipping_address': os.environ.get('STRIPE_ENABLE_SHIPPING_ADDRESS', False),
            }
        }
    },
    NETAXEPT: {
        'module': 'payment.gateways.netaxept',
        'config': {
            'auto_capture': True,
            'template_path': 'payment/netaxept.html',
            'connection_params': {
                'merchant_id': os.environ.get('NETAXEPT_MERCHANT_ID'),
                'token': os.environ.get('NETAXEPT_TOKEN'),
                'base_url': os.environ.get('NETAXEPT_BASE_URL') or 'https://test.epayment.nets.eu',
                'after_terminal_url': os.environ.get('NETAXEPT_AFTER_TERMINAL_URL'),
            }
        }
    },
}
