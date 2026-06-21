from django.shortcuts import render
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .emergency_detection import EMERGENCY_GUIDANCE, detect_emergency
from .intent_detection import detect_intent
from .models import ChatSession, EmergencyEvent, Message, Patient
from .serializers import (
    ChatSessionListSerializer,
    ChatSessionSerializer,
    MessageSerializer,
    PatientLoginSerializer,
    PatientProfileSerializer,
    PatientRegisterSerializer,
)


def register_page(request):
    return render(request, "patient/register.html")


def login_page(request):
    return render(request, "patient/login.html")


def profile_page(request):
    return render(request, "patient/profile.html")


def chat_page(request):
    return render(request, "patient/chat.html")


def _placeholder_bot_reply(session, patient_message: str) -> str:
    """Placeholder bot response until the LangGraph orchestrator is wired in."""
    message_count = session.messages.filter(sender="patient").count()
    name = session.patient.name.split()[0]
    if message_count == 1:
        return (
            f"Hello {name}, I'm MedicalBot — your AI medical assistant. "
            "I'm here to help collect information about your health concern before your doctor visit. "
            "Could you please tell me more about your main symptom or concern? "
            "For example: what is bothering you, how long has it been happening, and how severe is it?\n\n"
            "_This is not a replacement for a doctor. Please consult a qualified healthcare professional._"
        )
    return (
        "Thank you for sharing that. I've recorded your message. "
        "Please continue describing your symptoms and I'll collect the information for your doctor.\n\n"
        "_This is not a replacement for a doctor. Please consult a qualified healthcare professional._"
    )


class PatientRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = serializer.save()
        refresh = RefreshToken.for_user(patient)
        return Response(
            {
                "message": "Registration successful.",
                "patient_id": str(patient.patient_id),
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class PatientLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        patient = serializer.validated_data["patient"]
        refresh = RefreshToken.for_user(patient)
        return Response(
            {
                "patient_id": str(patient.patient_id),
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            }
        )


class PatientProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            patient = Patient.objects.get(pk=request.user.pk)
        except Patient.DoesNotExist:
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = PatientProfileSerializer(patient)
        return Response(serializer.data)


class ChatSessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            patient = Patient.objects.get(pk=request.user.pk)
        except Patient.DoesNotExist:
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)
        sessions = patient.chat_sessions.all()
        serializer = ChatSessionListSerializer(sessions, many=True)
        return Response(serializer.data)

    def post(self, request):
        try:
            patient = Patient.objects.get(pk=request.user.pk)
        except Patient.DoesNotExist:
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)
        session = ChatSession.objects.create(patient=patient)
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ChatSessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_session(self, request, session_id):
        try:
            patient = Patient.objects.get(pk=request.user.pk)
        except Patient.DoesNotExist:
            return None, Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            session = ChatSession.objects.get(id=session_id, patient=patient)
        except ChatSession.DoesNotExist:
            return None, Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
        return session, None

    def get(self, request, session_id):
        session, err = self._get_session(request, session_id)
        if err:
            return err
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data)

    def patch(self, request, session_id):
        """Mark a session as completed or abandoned."""
        session, err = self._get_session(request, session_id)
        if err:
            return err
        new_status = request.data.get("status")
        if new_status not in ("completed", "abandoned"):
            return Response({"error": "status must be 'completed' or 'abandoned'."}, status=status.HTTP_400_BAD_REQUEST)
        from django.utils import timezone
        session.status = new_status
        session.ended_at = timezone.now()
        session.save()
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data)


class ChatMessageCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            patient = Patient.objects.get(pk=request.user.pk)
        except Patient.DoesNotExist:
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            session = ChatSession.objects.get(id=session_id, patient=patient)
        except ChatSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)

        if session.status != "active":
            return Response({"error": "Cannot send messages to a closed session."}, status=status.HTTP_400_BAD_REQUEST)

        content = request.data.get("content", "").strip()
        if not content:
            return Response({"error": "Message content is required."}, status=status.HTTP_400_BAD_REQUEST)

        emergency_result = detect_emergency(content)
        if emergency_result["is_emergency"]:
            symptoms = emergency_result["symptoms_detected"]
            emergency_meta = {"emergency": True, "symptoms_detected": symptoms}
            patient_msg = Message.objects.create(
                session=session,
                sender="patient",
                content=content,
                metadata=emergency_meta,
            )
            EmergencyEvent.objects.create(
                session=session,
                patient=patient,
                trigger_message=content,
                symptoms_detected=symptoms,
                guidance_given=EMERGENCY_GUIDANCE,
            )
            session.risk_level = "emergency"
            session.save(update_fields=["risk_level"])
            bot_msg = Message.objects.create(
                session=session,
                sender="bot",
                content=EMERGENCY_GUIDANCE,
                agent_name="emergency_triage",
                metadata=emergency_meta,
            )
            return Response(
                {
                    "emergency": True,
                    "patient_message": MessageSerializer(patient_msg).data,
                    "bot_message": MessageSerializer(bot_msg).data,
                },
                status=status.HTTP_201_CREATED,
            )

        intent_result = detect_intent(content)

        patient_msg = Message.objects.create(
            session=session,
            sender="patient",
            content=content,
            metadata=intent_result,
        )

        session.session_metadata = {
            **session.session_metadata,
            "last_intent": intent_result["intent"],
            "last_confidence": intent_result["confidence"],
        }
        session.save()

        bot_reply_text = _placeholder_bot_reply(session, content)
        bot_msg = Message.objects.create(session=session, sender="bot", content=bot_reply_text, agent_name="placeholder")

        return Response(
            {
                "emergency": False,
                "patient_message": MessageSerializer(patient_msg).data,
                "bot_message": MessageSerializer(bot_msg).data,
            },
            status=status.HTTP_201_CREATED,
        )


class PatientLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)
