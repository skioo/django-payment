"""test_payments URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from .views import paybox_system, paybox_system_subscription, paybox_direct, paybox_direct_3d, paybox_direct_plus

urlpatterns = [
    path('admin/', admin.site.urls),
    path('paybox-system/', paybox_system),
    path('paybox-system-subscription/', paybox_system_subscription),
    path('paybox-direct/', paybox_direct),
    path('paybox-direct-3d/', paybox_direct_3d),
    path('paybox-direct-plus/', paybox_direct_plus)
]
