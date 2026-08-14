from django.urls import path

from .views import (
    DoctorAppointmentDetailView,
    DoctorAppointmentListView,
    DoctorLoginView,
    DoctorNoteDetailView,
    DoctorNoteListCreateView,
    DoctorProfileView,
    DoctorRegisterView,
    PatientSessionDetailForDoctorView,
    PatientSessionListView,
    PrescriptionDetailView,
    PrescriptionListCreateView,
    SessionAssignView,
)

urlpatterns = [
    path("register/", DoctorRegisterView.as_view(), name="doctor-register"),
    path("login/", DoctorLoginView.as_view(), name="doctor-login"),
    path("profile/", DoctorProfileView.as_view(), name="doctor-profile"),
    path("patients/sessions/", PatientSessionListView.as_view(), name="doctor-patient-sessions"),
    path("patients/sessions/<uuid:session_id>/", PatientSessionDetailForDoctorView.as_view(), name="doctor-patient-session-detail"),
    path("patients/sessions/<uuid:session_id>/assign/", SessionAssignView.as_view(), name="doctor-session-assign"),
    path("appointments/", DoctorAppointmentListView.as_view(), name="doctor-appointments"),
    path("appointments/<uuid:appointment_id>/", DoctorAppointmentDetailView.as_view(), name="doctor-appointment-detail"),
    path("patients/sessions/<uuid:session_id>/notes/", DoctorNoteListCreateView.as_view(), name="doctor-session-notes"),
    path("patients/sessions/<uuid:session_id>/notes/<uuid:note_id>/", DoctorNoteDetailView.as_view(), name="doctor-session-note-detail"),
    path("patients/sessions/<uuid:session_id>/prescriptions/", PrescriptionListCreateView.as_view(), name="doctor-session-prescriptions"),
    path("patients/sessions/<uuid:session_id>/prescriptions/<uuid:prescription_id>/", PrescriptionDetailView.as_view(), name="doctor-session-prescription-detail"),
]
