"""
URL configuration for MedicalBot project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
from django.urls import include, path

from patient.views import login_page, register_page

from .views import api_root, home

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    # Patient pages
    path("patient/register/", register_page, name="patient-register-page"),
    path("patient/login/", login_page, name="patient-login-page"),
    # API
    path("api/", api_root, name="api-root"),
    path("api/patient/", include("patient.urls")),
]
