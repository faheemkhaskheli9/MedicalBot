from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from patient.models import Appointment, ChatSession
from patient.serializers import AppointmentSerializer

from .models import Doctor, DoctorNote
from .serializers import (
    DoctorAppointmentSerializer,
    DoctorLoginSerializer,
    DoctorNoteSerializer,
    DoctorProfileSerializer,
    DoctorRegisterSerializer,
    PatientSessionDetailSerializer,
    PatientSessionListSerializer,
)


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

        serializer = PatientSessionListSerializer(sessions, many=True)
        return Response(serializer.data)


class PatientSessionDetailForDoctorView(APIView):
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

        return Response(PatientSessionDetailSerializer(session).data)


class DoctorNoteListCreateView(APIView):
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
        return Response(DoctorNoteSerializer(note).data, status=status.HTTP_201_CREATED)


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


class SessionAssignView(APIView):
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
        return Response(status=status.HTTP_204_NO_CONTENT)


class DoctorNoteDetailView(APIView):
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
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
