from django.urls import path

from .views import (
    DoctorLoginView,
    DoctorProfileView,
    DoctorRegisterView,
    PatientSessionDetailForDoctorView,
    PatientSessionListView,
)

urlpatterns = [
    path("register/", DoctorRegisterView.as_view(), name="doctor-register"),
    path("login/", DoctorLoginView.as_view(), name="doctor-login"),
    path("profile/", DoctorProfileView.as_view(), name="doctor-profile"),
    path("patients/sessions/", PatientSessionListView.as_view(), name="doctor-patient-sessions"),
    path("patients/sessions/<uuid:session_id>/", PatientSessionDetailForDoctorView.as_view(), name="doctor-patient-session-detail"),
]
