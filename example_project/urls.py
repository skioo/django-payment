from django.contrib import admin
from django.urls import path, include

import views
from views import netaxept
from views import stripe

example_urlpatterns = [
    path('', views.list_payments, name='list_payments'),
    path('<payment_id>', views.view_payment, name='view_payment'),
    path('stripe/', include(stripe.urls)),
    path('netaxept/', include(netaxept.urls)),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('payment/', include('payment.urls')),
    path('example/', include(example_urlpatterns)),
]
