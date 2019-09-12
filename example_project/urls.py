from django.contrib import admin
from django.urls import path, include

import views
from views import stripe

example_urlpatterns = [
    path('<payment_id>', views.view_payment, name='view_payment'),
    path('<payment_id>/capture', views.capture, name='capture'),
    path('stripe/', include(stripe.urls)),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('payment/', include('payment.urls')),
    path('example/', include(example_urlpatterns)),
]
