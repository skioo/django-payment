# Netaxept

## Configuration

In the PAYMENT_GATEWAYS setting, configure the netaxept connection params:

`merchant_id`, `secret`, `base_url`, and `after_terminal_url`.

The production base_url is:

`https://epayment.nets.eu/`


## Design

Netaxept works by taking the user to a hosted page and then redirecting the user to the merchant in order to finish 
processing the payment.
We chose not to provide such a view in the payment application (we do provide an example view in the example_project),
This means a project that uses netaxept payment will have to implement its own after_terminal view.

- The first reason is that it's not possible to design a simple, generic response that we can show to users of the 
application (because we don't know anything about the application)
- The second reason is that after a successful payment something more than just acknowledging the payment 
usually needs to happen in the application (for instance setting the status of an order, sending an email, etc).

It's not impossible to solve those two problems with configuration, application-provided functions, and signals
but it doesn't seem like all this complexity is worth it, compared to reimplementing a simple, straightforward webhook.
