from django.urls import path

from .views import PatientLoginView, PatientProfileView, PatientRegisterView

urlpatterns = [
    path("register/", PatientRegisterView.as_view(), name="patient-register"),
    path("login/", PatientLoginView.as_view(), name="patient-login"),
    path("profile/", PatientProfileView.as_view(), name="patient-profile"),
]
