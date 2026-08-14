from django.shortcuts import render
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from patient.models import Appointment, ChatSession
from patient.serializers import AppointmentSerializer

from .models import AIDiagnosisSuggestion, AuditLog, Doctor, DoctorNote, Prescription
from .serializers import (
    AIDiagnosisSuggestionSerializer,
    DoctorAppointmentSerializer,
    DoctorLoginSerializer,
    DoctorNoteSerializer,
    DoctorProfileSerializer,
    DoctorRegisterSerializer,
    PatientSessionDetailSerializer,
    PatientSessionListSerializer,
    PrescriptionSerializer,
)


class AuditLogMixin:
    def _log(self, request, action: str, target_type: str, target_id):
        try:
            AuditLog.objects.create(
                actor=request.user,
                action=action,
                target_type=target_type,
                target_id=str(target_id),
            )
        except Exception:
            pass


class DoctorRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DoctorRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doctor = serializer.save()
        refresh = RefreshToken.for_user(doctor)
        return Response(
            {
                "message": "Doctor registration successful.",
                "doctor_id": doctor.pk,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class DoctorLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DoctorLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        doctor = serializer.validated_data["doctor"]
        refresh = RefreshToken.for_user(doctor)
        return Response(
            {
                "doctor_id": doctor.pk,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            }
        )


class DoctorProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            doctor = Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(DoctorProfileSerializer(doctor).data)


class PatientSessionListView(APIView):
    """List all patient sessions visible to the authenticated doctor."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)

        risk_level = request.query_params.get("risk_level")
        sess_status = request.query_params.get("status")

        sessions = ChatSession.objects.select_related("patient").order_by("-started_at")
        if risk_level:
            sessions = sessions.filter(risk_level=risk_level)
        if sess_status:
            sessions = sessions.filter(status=sess_status)

        if request.query_params.get("ai_prioritized") == "true":
            RISK_ORDER = {"emergency": 0, "urgent": 1, "routine": 2, None: 3}
            sessions = sorted(
                sessions,
                key=lambda s: (
                    RISK_ORDER.get(s.risk_level, 3),
                    0 if s.assigned_doctor_id is None else 1,
                    s.started_at,
                ),
            )

        serializer = PatientSessionListSerializer(sessions, many=True)
        return Response(serializer.data)


class PatientSessionDetailForDoctorView(AuditLogMixin, APIView):
    """Full session detail (with summary and transcript) for the authenticated doctor."""
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        try:
            Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            session = ChatSession.objects.select_related("patient").get(id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)

        self._log(request, "view_session", "session", session_id)
        return Response(PatientSessionDetailSerializer(session).data)


class DoctorNoteListCreateView(AuditLogMixin, APIView):
    """List all notes on a session or add a new note (doctor only)."""
    permission_classes = [IsAuthenticated]

    def _get_doctor_and_session(self, request, session_id):
        try:
            doctor = Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return None, None, Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return None, None, Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
        return doctor, session, None

    def get(self, request, session_id):
        doctor, session, err = self._get_doctor_and_session(request, session_id)
        if err:
            return err
        notes = DoctorNote.objects.filter(session=session).select_related("doctor")
        return Response(DoctorNoteSerializer(notes, many=True).data)

    def post(self, request, session_id):
        doctor, session, err = self._get_doctor_and_session(request, session_id)
        if err:
            return err
        serializer = DoctorNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = DoctorNote.objects.create(
            session=session,
            doctor=doctor,
            note=serializer.validated_data["note"],
        )
        self._log(request, "create_note", "note", note.id)
        return Response(DoctorNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class PrescriptionListCreateView(AuditLogMixin, APIView):
    """Doctor creates/lists prescriptions for a patient session."""
    permission_classes = [IsAuthenticated]

    def _get_doctor_and_session(self, request, session_id):
        try:
            doctor = Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return None, None, Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return None, None, Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
        return doctor, session, None

    def get(self, request, session_id):
        doctor, session, err = self._get_doctor_and_session(request, session_id)
        if err:
            return err
        prescriptions = Prescription.objects.filter(session=session).select_related("doctor")
        return Response(PrescriptionSerializer(prescriptions, many=True).data)

    def post(self, request, session_id):
        doctor, session, err = self._get_doctor_and_session(request, session_id)
        if err:
            return err
        serializer = PrescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prescription = serializer.save(doctor=doctor, session=session)
        self._log(request, "create_prescription", "prescription", prescription.id)
        return Response(PrescriptionSerializer(prescription).data, status=status.HTTP_201_CREATED)


class PrescriptionDetailView(AuditLogMixin, APIView):
    """Retrieve or update a single prescription (only the authoring doctor may update)."""
    permission_classes = [IsAuthenticated]

    def _get_doctor_and_prescription(self, request, session_id, prescription_id):
        try:
            doctor = Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return None, None, Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            prescription = Prescription.objects.select_related("doctor").get(
                id=prescription_id, session_id=session_id
            )
        except Prescription.DoesNotExist:
            return None, None, Response({"error": "Prescription not found."}, status=status.HTTP_404_NOT_FOUND)
        return doctor, prescription, None

    def get(self, request, session_id, prescription_id):
        _, prescription, err = self._get_doctor_and_prescription(request, session_id, prescription_id)
        if err:
            return err
        return Response(PrescriptionSerializer(prescription).data)

    def patch(self, request, session_id, prescription_id):
        doctor, prescription, err = self._get_doctor_and_prescription(request, session_id, prescription_id)
        if err:
            return err
        if prescription.doctor_id != doctor.pk:
            return Response(
                {"error": "You can only edit your own prescriptions."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = PrescriptionSerializer(prescription, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PrescriptionSerializer(prescription).data)

    def delete(self, request, session_id, prescription_id):
        doctor, prescription, err = self._get_doctor_and_prescription(request, session_id, prescription_id)
        if err:
            return err
        if prescription.doctor_id != doctor.pk:
            return Response(
                {"error": "You can only delete your own prescriptions."},
                status=status.HTTP_403_FORBIDDEN,
            )
        self._log(request, "delete_prescription", "prescription", prescription_id)
        prescription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DoctorAppointmentListView(APIView):
    """Doctor can list their appointments, optionally filtered by status."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            doctor = Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)
        apt_status = request.query_params.get("status")
        appointments = doctor.appointments.select_related("patient").order_by("scheduled_at")
        if apt_status:
            appointments = appointments.filter(status=apt_status)
        return Response(DoctorAppointmentSerializer(appointments, many=True).data)


class DoctorAppointmentDetailView(APIView):
    """Doctor can confirm, complete, or cancel an appointment and add notes."""
    permission_classes = [IsAuthenticated]

    ALLOWED_STATUS_TRANSITIONS = {
        "pending": {"confirmed", "cancelled"},
        "confirmed": {"completed", "cancelled"},
    }

    def _get_doctor_and_appointment(self, request, appointment_id):
        try:
            doctor = Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return None, None, Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            appointment = Appointment.objects.select_related("patient").get(id=appointment_id, doctor=doctor)
        except Appointment.DoesNotExist:
            return None, None, Response({"error": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)
        return doctor, appointment, None

    def get(self, request, appointment_id):
        _, appointment, err = self._get_doctor_and_appointment(request, appointment_id)
        if err:
            return err
        return Response(DoctorAppointmentSerializer(appointment).data)

    def patch(self, request, appointment_id):
        _, appointment, err = self._get_doctor_and_appointment(request, appointment_id)
        if err:
            return err
        new_status = request.data.get("status")
        doctor_notes = request.data.get("doctor_notes")
        if new_status:
            allowed = self.ALLOWED_STATUS_TRANSITIONS.get(appointment.status, set())
            if new_status not in allowed:
                return Response(
                    {"error": f"Cannot transition from '{appointment.status}' to '{new_status}'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            appointment.status = new_status
        if doctor_notes is not None:
            appointment.doctor_notes = doctor_notes
        appointment.save()
        return Response(DoctorAppointmentSerializer(appointment).data)


class SessionAssignView(AuditLogMixin, APIView):
    """Assign (POST) or unassign (DELETE) the requesting doctor from a session."""
    permission_classes = [IsAuthenticated]

    def _get_doctor_and_session(self, request, session_id):
        try:
            doctor = Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return None, None, Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return None, None, Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
        return doctor, session, None

    def post(self, request, session_id):
        doctor, session, err = self._get_doctor_and_session(request, session_id)
        if err:
            return err
        if session.assigned_doctor_id and session.assigned_doctor_id != doctor.pk:
            return Response(
                {"error": "Session is already assigned to another doctor."},
                status=status.HTTP_409_CONFLICT,
            )
        session.assigned_doctor = doctor
        session.save(update_fields=["assigned_doctor"])
        self._log(request, "assign_session", "session", session_id)
        return Response(
            {
                "message": "Session assigned successfully.",
                "session_id": str(session.id),
                "assigned_doctor": {"id": doctor.pk, "name": doctor.name},
            }
        )

    def delete(self, request, session_id):
        doctor, session, err = self._get_doctor_and_session(request, session_id)
        if err:
            return err
        if session.assigned_doctor_id != doctor.pk:
            return Response(
                {"error": "You are not assigned to this session."},
                status=status.HTTP_403_FORBIDDEN,
            )
        session.assigned_doctor = None
        session.save(update_fields=["assigned_doctor"])
        self._log(request, "unassign_session", "session", session_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DoctorNoteDetailView(AuditLogMixin, APIView):
    """Retrieve or delete a single note (only the authoring doctor may delete)."""
    permission_classes = [IsAuthenticated]

    def _get_doctor_and_note(self, request, session_id, note_id):
        try:
            doctor = Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return None, None, Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            note = DoctorNote.objects.select_related("doctor").get(id=note_id, session_id=session_id)
        except DoctorNote.DoesNotExist:
            return None, None, Response({"error": "Note not found."}, status=status.HTTP_404_NOT_FOUND)
        return doctor, note, None

    def get(self, request, session_id, note_id):
        _, note, err = self._get_doctor_and_note(request, session_id, note_id)
        if err:
            return err
        return Response(DoctorNoteSerializer(note).data)

    def delete(self, request, session_id, note_id):
        doctor, note, err = self._get_doctor_and_note(request, session_id, note_id)
        if err:
            return err
        if note.doctor_id != doctor.pk:
            return Response({"error": "You can only delete your own notes."}, status=status.HTTP_403_FORBIDDEN)
        self._log(request, "delete_note", "note", note_id)
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Phase 3 — Doctor AI Views ─────────────────────────────────────────────────

class AIDiagnosisView(AuditLogMixin, APIView):
    """Generate and store an AI differential diagnosis for a session."""
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            doctor = Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            session = ChatSession.objects.select_related("patient").get(id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)

        from .ai_features import generate_differential_diagnosis
        try:
            content = generate_differential_diagnosis(session, doctor)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"error": "Failed to generate diagnosis suggestions. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        suggestion = AIDiagnosisSuggestion.objects.create(
            session=session, doctor=doctor, content=content
        )
        self._log(request, "generate_diagnosis", "session", session_id)
        return Response(AIDiagnosisSuggestionSerializer(suggestion).data, status=status.HTTP_201_CREATED)


class DoctorNoteDraftView(APIView):
    """Generate an AI SOAP note draft for a session (requires clinical summary)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            session = ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)

        from .ai_features import generate_soap_draft
        try:
            draft = generate_soap_draft(session)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"error": "Failed to generate note draft. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"draft": draft})


class DrugInteractionCheckView(APIView):
    """Check proposed medications for interactions with the patient's current medications."""
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            session = ChatSession.objects.select_related("patient").get(id=session_id)
        except ChatSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)

        medications = request.data.get("medications", [])
        if not isinstance(medications, list) or not medications:
            return Response(
                {"error": "medications must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .ai_features import check_drug_interactions
        try:
            result = check_drug_interactions(medications, str(session.patient.patient_id))
        except Exception:
            return Response(
                {"error": "Failed to check drug interactions. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(result)


class PatientCrossSummaryView(APIView):
    """Return a cross-session summary of a patient's health history for a doctor."""
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        try:
            Doctor.objects.get(pk=request.user.pk)
        except Doctor.DoesNotExist:
            return Response({"error": "Doctor profile not found."}, status=status.HTTP_404_NOT_FOUND)

        from patient.models import Patient
        try:
            patient = Patient.objects.get(patient_id=patient_id)
        except Patient.DoesNotExist:
            return Response({"error": "Patient not found."}, status=status.HTTP_404_NOT_FOUND)

        sessions_with_summaries = list(
            patient.chat_sessions.exclude(summary__isnull=True).order_by("started_at")
        )

        analyze = request.query_params.get("analyze", "true").lower() != "false"

        if not sessions_with_summaries:
            return Response({
                "patient_name": patient.name,
                "session_count": 0,
                "date_range": None,
                "sessions": [],
                "trend_analysis": None,
            })

        from .ai_features import generate_cross_session_summary
        if analyze:
            try:
                result = generate_cross_session_summary(patient, sessions_with_summaries)
            except Exception:
                analyze = False

        if not analyze:
            # Return basic timeline without LLM call
            entries = [
                {
                    "session_id": str(s.id),
                    "date": s.started_at.isoformat(),
                    "risk_level": s.risk_level,
                    "chief_complaint": s.summary.get("chief_complaint"),
                    "recommended_action": s.summary.get("recommended_action"),
                    "notes_for_doctor": s.summary.get("notes_for_doctor"),
                }
                for s in sessions_with_summaries
            ]
            dates = [s.started_at.isoformat() for s in sessions_with_summaries]
            result = {
                "patient_name": patient.name,
                "session_count": len(entries),
                "date_range": {"from": dates[0], "to": dates[-1]} if dates else None,
                "sessions": entries,
                "trend_analysis": None,
            }

        return Response(result)


def doctor_login_page(request):
    return render(request, "doctor/login.html")


def doctor_register_page(request):
    return render(request, "doctor/register.html")


def doctor_dashboard_page(request):
    return render(request, "doctor/dashboard.html")
