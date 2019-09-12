#!/usr/bin/env python
from setuptools import setup

setup(
    name='django-payment',
    version='1.0',
    description='',
    long_description='',
    author='Nicholas Wolff',
    author_email='nwolff@gmail.com',
    url='https://github.com/skioo/django-payment',
    download_url='https://pypi.python.org/pypi/django-payment',
    packages=[
        'payment',
        'payment.gateways',
        'payment.gateways.dummy',
        'payment.gateways.stripe',
        'payment.migrations',
    ],
    package_data={
        'payment': [
            'locale/*/LC_MESSAGES/*.*',
            'templates/admin/payment/*.html',
        ]
    },
    install_requires=[
        'Django>=2.2,<2.3',
        'django-money',
        'structlog',
        'typing',
        'stripe',
        'django-countries',
        'dataclasses',
        'django-import-export',
    ],
    license='MIT',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Framework :: Django :: 2.2',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)