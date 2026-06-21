from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from patient.models import ChatSession

from .models import Doctor
from .serializers import (
    DoctorLoginSerializer,
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
