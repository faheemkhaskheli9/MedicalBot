from django.urls import path

from .views import (
    ChatMessageCreateView,
    ChatSessionDetailView,
    ChatSessionListCreateView,
    ChatSessionSummaryView,
    MedicalHistoryView,
    PatientLoginView,
    PatientLogoutView,
    PatientProfileView,
    PatientRegisterView,
)

urlpatterns = [
    path("register/", PatientRegisterView.as_view(), name="patient-register"),
    path("login/", PatientLoginView.as_view(), name="patient-login"),
    path("logout/", PatientLogoutView.as_view(), name="patient-logout"),
    path("profile/", PatientProfileView.as_view(), name="patient-profile"),
    path("chat/sessions/", ChatSessionListCreateView.as_view(), name="chat-sessions"),
    path("chat/sessions/<uuid:session_id>/", ChatSessionDetailView.as_view(), name="chat-session-detail"),
    path("chat/sessions/<uuid:session_id>/messages/", ChatMessageCreateView.as_view(), name="chat-messages"),
    path("chat/sessions/<uuid:session_id>/summary/", ChatSessionSummaryView.as_view(), name="chat-session-summary"),
    path("medical-history/", MedicalHistoryView.as_view(), name="patient-medical-history"),
]
