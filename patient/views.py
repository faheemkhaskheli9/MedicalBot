from django.shortcuts import render
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .agents.runner import run_triage_graph
from .emergency_detection import EMERGENCY_GUIDANCE, detect_emergency
from .intent_detection import detect_intent
from .models import Appointment, ChatSession, EmergencyEvent, MedicalHistory, Message, Patient, Recommendation
from .services import build_conversation_history, summarize_session_if_needed
from .summary import generate_session_summary
from .serializers import (
    AppointmentSerializer,
    ChatSessionListSerializer,
    ChatSessionSerializer,
    MedicalHistorySerializer,
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
    from .throttles import PatientChatThrottle
    throttle_classes = [PatientChatThrottle]

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
        low_confidence = intent_result["confidence"] < 0.6

        patient_meta = {**intent_result}
        if low_confidence:
            patient_meta["low_confidence"] = True

        patient_msg = Message.objects.create(
            session=session,
            sender="patient",
            content=content,
            metadata=patient_meta,
        )

        # Build history using compressed summary + recent messages (Phase 1.3)
        history = build_conversation_history(session)

        graph_result = run_triage_graph(
            conversation_history=history,
            intent=intent_result["intent"],
            patient_name=session.patient.name,
            session_metadata=session.session_metadata,
            patient_id=str(patient.patient_id),
        )

        session.session_metadata = {
            **session.session_metadata,
            "last_intent": intent_result["intent"],
            "last_confidence": intent_result["confidence"],
            "last_agent": graph_result["agent_used"],
        }
        if graph_result["risk_level"]:
            session.risk_level = graph_result["risk_level"]
        session.save()

        bot_meta = {}
        if graph_result["agent_used"] == "fallback":
            bot_meta["triage_fallback"] = True

        bot_msg = Message.objects.create(
            session=session,
            sender="bot",
            content=graph_result["bot_response"],
            agent_name=graph_result["agent_used"],
            metadata=bot_meta if bot_meta else None,
        )

        summarize_session_if_needed(session)

        return Response(
            {
                "emergency": False,
                "patient_message": MessageSerializer(patient_msg).data,
                "bot_message": MessageSerializer(bot_msg).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ChatSessionSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    from .throttles import PatientSummaryThrottle
    throttle_classes = [PatientSummaryThrottle]

    def post(self, request, session_id):
        try:
            patient = Patient.objects.get(pk=request.user.pk)
        except Patient.DoesNotExist:
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            session = ChatSession.objects.get(id=session_id, patient=patient)
        except ChatSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)

        if session.status == "abandoned":
            return Response(
                {"error": "Cannot summarise an abandoned session."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        patient_messages = session.messages.filter(sender="patient")
        if patient_messages.count() < 2:
            return Response(
                {"error": "At least 2 patient messages are required to generate a summary."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        history = [
            {
                "role": "user" if msg.sender == "patient" else "assistant",
                "content": msg.content,
            }
            for msg in session.messages.order_by("created_at")
        ]

        try:
            summary = generate_session_summary(
                conversation_history=history,
                patient_name=patient.name,
                patient_age=patient.age,
            )
        except Exception:
            return Response(
                {"error": "Failed to generate summary. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        session.summary = summary
        if summary.get("risk_level") in ("routine", "urgent", "emergency"):
            session.risk_level = summary["risk_level"]
        session.save(update_fields=["summary", "risk_level"])

        return Response({"summary": summary}, status=status.HTTP_200_OK)


class MedicalHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_patient(self, request):
        try:
            return Patient.objects.get(pk=request.user.pk), None
        except Patient.DoesNotExist:
            return None, Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request):
        patient, err = self._get_patient(request)
        if err:
            return err
        history, _ = MedicalHistory.objects.get_or_create(patient=patient)
        return Response(MedicalHistorySerializer(history).data)

    def put(self, request):
        patient, err = self._get_patient(request)
        if err:
            return err
        history, _ = MedicalHistory.objects.get_or_create(patient=patient)
        serializer = MedicalHistorySerializer(history, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request):
        patient, err = self._get_patient(request)
        if err:
            return err
        history, _ = MedicalHistory.objects.get_or_create(patient=patient)
        serializer = MedicalHistorySerializer(history, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PatientPrescriptionListView(APIView):
    """Patient reads all prescriptions across their sessions."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            patient = Patient.objects.get(pk=request.user.pk)
        except Patient.DoesNotExist:
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)
        from doctor.models import Prescription
        from doctor.serializers import PrescriptionSerializer
        prescriptions = Prescription.objects.filter(
            session__patient=patient
        ).select_related("doctor", "session").order_by("-created_at")
        return Response(PrescriptionSerializer(prescriptions, many=True).data)


class PatientSessionPrescriptionListView(APIView):
    """Patient reads prescriptions for a specific session."""
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        try:
            patient = Patient.objects.get(pk=request.user.pk)
        except Patient.DoesNotExist:
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            session = ChatSession.objects.get(id=session_id, patient=patient)
        except ChatSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)
        from doctor.models import Prescription
        from doctor.serializers import PrescriptionSerializer
        prescriptions = Prescription.objects.filter(session=session).select_related("doctor")
        return Response(PrescriptionSerializer(prescriptions, many=True).data)


class AppointmentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_patient(self, request):
        try:
            return Patient.objects.get(pk=request.user.pk), None
        except Patient.DoesNotExist:
            return None, Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request):
        patient, err = self._get_patient(request)
        if err:
            return err
        apt_status = request.query_params.get("status")
        appointments = patient.appointments.select_related("doctor", "session")
        if apt_status:
            appointments = appointments.filter(status=apt_status)
        return Response(AppointmentSerializer(appointments, many=True).data)

    def post(self, request):
        patient, err = self._get_patient(request)
        if err:
            return err
        serializer = AppointmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from doctor.models import Doctor
        doctor_id = serializer.validated_data["doctor"].pk
        try:
            doctor = Doctor.objects.get(pk=doctor_id)
        except Doctor.DoesNotExist:
            return Response({"error": "Doctor not found."}, status=status.HTTP_404_NOT_FOUND)
        appointment = serializer.save(patient=patient, doctor=doctor)
        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)


class AppointmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_patient_and_appointment(self, request, appointment_id):
        try:
            patient = Patient.objects.get(pk=request.user.pk)
        except Patient.DoesNotExist:
            return None, None, Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            appointment = Appointment.objects.select_related("doctor", "session").get(id=appointment_id, patient=patient)
        except Appointment.DoesNotExist:
            return None, None, Response({"error": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)
        return patient, appointment, None

    def get(self, request, appointment_id):
        _, appointment, err = self._get_patient_and_appointment(request, appointment_id)
        if err:
            return err
        return Response(AppointmentSerializer(appointment).data)

    def delete(self, request, appointment_id):
        _, appointment, err = self._get_patient_and_appointment(request, appointment_id)
        if err:
            return err
        if appointment.status not in ("pending",):
            return Response(
                {"error": "Only pending appointments can be cancelled by the patient."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        appointment.status = "cancelled"
        appointment.save(update_fields=["status", "updated_at"])
        return Response(AppointmentSerializer(appointment).data)


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


# ── Phase 2 — New Patient AI Views ────────────────────────────────────────────

class ChatSessionRecommendationsView(APIView):
    """Generate and store AI follow-up recommendations for a session (requires clinical summary)."""
    permission_classes = [IsAuthenticated]
    from .throttles import PatientSummaryThrottle
    throttle_classes = [PatientSummaryThrottle]

    def post(self, request, session_id):
        try:
            patient = Patient.objects.get(pk=request.user.pk)
        except Patient.DoesNotExist:
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            session = ChatSession.objects.get(id=session_id, patient=patient)
        except ChatSession.DoesNotExist:
            return Response({"error": "Session not found."}, status=status.HTTP_404_NOT_FOUND)

        from .recommendations import generate_recommendations
        from .serializers import RecommendationSerializer
        try:
            content = generate_recommendations(session, patient)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"error": "Failed to generate recommendations. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        rec, _ = Recommendation.objects.update_or_create(
            session=session,
            defaults={"content": content},
        )
        return Response(RecommendationSerializer(rec).data, status=status.HTTP_201_CREATED)


class PatientPrescriptionExplainView(APIView):
    """Return a plain-language AI explanation of a specific prescription."""
    permission_classes = [IsAuthenticated]

    def get(self, request, prescription_id):
        try:
            patient = Patient.objects.get(pk=request.user.pk)
        except Patient.DoesNotExist:
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)

        from doctor.models import Prescription
        try:
            prescription = Prescription.objects.select_related("doctor").get(
                id=prescription_id, session__patient=patient
            )
        except Prescription.DoesNotExist:
            return Response({"error": "Prescription not found."}, status=status.HTTP_404_NOT_FOUND)

        import json
        from .llm_client import get_llm_provider

        system_prompt = (
            "You are a patient education assistant. Explain the following prescription in plain, "
            "easy-to-understand language. For each medication, describe: what it is generally used for, "
            "how it is typically taken, common side effects to watch for, and any important safety notes. "
            "Keep the tone reassuring and clear. Always advise the patient to follow their doctor's "
            "specific instructions and contact them with questions."
        )
        user_content = (
            f"Medications: {json.dumps(prescription.medications)}\n"
            f"Instructions: {prescription.instructions or 'None provided'}"
        )
        try:
            explanation = get_llm_provider().complete([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ])
        except Exception:
            return Response(
                {"error": "Failed to generate explanation. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"explanation": explanation})


class PatientSymptomHistoryView(APIView):
    """Return a chronological timeline of symptom summaries across all the patient's sessions."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            patient = Patient.objects.get(pk=request.user.pk)
        except Patient.DoesNotExist:
            return Response({"error": "Patient profile not found."}, status=status.HTTP_404_NOT_FOUND)

        sessions_with_summary = (
            patient.chat_sessions
            .exclude(summary__isnull=True)
            .order_by("started_at")
        )

        timeline = []
        for s in sessions_with_summary:
            entry = {
                "session_id": str(s.id),
                "date": s.started_at.isoformat(),
                "risk_level": s.risk_level,
                "chief_complaint": s.summary.get("chief_complaint"),
                "symptom_details": s.summary.get("symptom_details"),
                "recommended_action": s.summary.get("recommended_action"),
            }
            timeline.append(entry)

        trend_analysis = None
        if request.query_params.get("analyze", "false").lower() == "true" and len(timeline) >= 2:
            from .llm_client import get_llm_provider
            import json
            system_prompt = (
                "You are a medical data analyst. Given a patient's symptom history timeline, "
                "identify recurring complaints, trends over time, and any patterns worth noting. "
                "Be concise (3-5 sentences). Do NOT diagnose."
            )
            user_content = f"Symptom history:\n{json.dumps(timeline, indent=2)}"
            try:
                trend_analysis = get_llm_provider().complete([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ])
            except Exception:
                trend_analysis = None

        return Response({"timeline": timeline, "trend_analysis": trend_analysis})
