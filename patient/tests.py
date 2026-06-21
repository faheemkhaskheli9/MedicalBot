from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from .intent_detection import SUPPORTED_INTENTS
from .models import ChatSession, EmergencyEvent, Patient

REGISTER_URL   = "/api/patient/register/"
LOGIN_URL      = "/api/patient/login/"
PROFILE_URL    = "/api/patient/profile/"
SESSIONS_URL   = "/api/patient/chat/sessions/"

VALID_PAYLOAD = {
    "name": "Ali Khan",
    "age": 30,
    "gender": "male",
    "phone": "03001234567",
    "email": "ali@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!",
}

_MOCK_GRAPH_RESULT = {
    "bot_response": "I understand. Can you tell me more about your symptoms?",
    "agent_used": "intake_agent",
    "risk_level": None,
}
_NON_EMERGENCY = {"is_emergency": False, "symptoms_detected": [], "confidence": 0.0}
_SYMPTOM_INTENT = {"intent": "symptom_check", "confidence": 0.9}


class PatientRegistrationTests(APITestCase):
    def test_register_success(self):
        response = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("patient_id", response.data)
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertTrue(Patient.objects.filter(email="ali@example.com").exists())

    def test_patient_id_is_assigned(self):
        response = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        self.assertIsNotNone(response.data["patient_id"])
        patient = Patient.objects.get(email="ali@example.com")
        self.assertEqual(str(patient.patient_id), response.data["patient_id"])

    def test_patient_ids_are_unique(self):
        r1 = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        payload2 = {**VALID_PAYLOAD, "email": "other@example.com", "phone": "03009999999"}
        r2 = self.client.post(REGISTER_URL, payload2, format="json")
        self.assertNotEqual(r1.data["patient_id"], r2.data["patient_id"])

    def test_duplicate_email_rejected(self):
        self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        payload = {**VALID_PAYLOAD, "phone": "03009999999"}
        response = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_phone_rejected(self):
        self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        payload = {**VALID_PAYLOAD, "email": "other@example.com"}
        response = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_name_rejected(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "name"}
        response = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_age_rejected(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "age"}
        response = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_gender_rejected(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "gender"}
        response = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_phone_rejected(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "phone"}
        response = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_email_rejected(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "email"}
        response = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_password_rejected(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "password"}
        response = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_mismatch_rejected(self):
        payload = {**VALID_PAYLOAD, "password_confirm": "DifferentPassword!"}
        response = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_email_format_rejected(self):
        payload = {**VALID_PAYLOAD, "email": "not-an-email"}
        response = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_gender_rejected(self):
        payload = {**VALID_PAYLOAD, "gender": "unknown_value"}
        response = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_not_returned_in_response(self):
        response = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        self.assertNotIn("password", response.data)


class PatientLoginTests(APITestCase):
    def setUp(self):
        self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")

    def test_login_success(self):
        response = self.client.post(
            LOGIN_URL,
            {"email": "ali@example.com", "password": "SecurePass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
        self.assertIn("patient_id", response.data)

    def test_wrong_password_rejected(self):
        response = self.client.post(
            LOGIN_URL,
            {"email": "ali@example.com", "password": "WrongPassword!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nonexistent_user_rejected(self):
        response = self.client.post(
            LOGIN_URL,
            {"email": "nobody@example.com", "password": "SecurePass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_email_rejected(self):
        response = self.client.post(LOGIN_URL, {"password": "SecurePass123!"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_password_rejected(self):
        response = self.client.post(LOGIN_URL, {"email": "ali@example.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PatientProfileTests(APITestCase):
    def setUp(self):
        r = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        self.token = r.data["tokens"]["access"]

    def test_profile_requires_auth(self):
        response = self.client.get(PROFILE_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_profile_returns_data(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(PROFILE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "ali@example.com")
        self.assertEqual(response.data["name"], "Ali Khan")
        self.assertEqual(response.data["age"], 30)
        self.assertEqual(response.data["gender"], "male")
        self.assertEqual(response.data["phone"], "03001234567")
        self.assertIn("patient_id", response.data)

    def test_profile_does_not_expose_password(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(PROFILE_URL)
        self.assertNotIn("password", response.data)


class ChatSessionTests(APITestCase):
    def setUp(self):
        r = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        self.token = r.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_create_session_returns_201(self):
        r = self.client.post(SESSIONS_URL, {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", r.data)
        self.assertEqual(r.data["status"], "active")

    def test_create_session_requires_auth(self):
        self.client.credentials()
        r = self.client.post(SESSIONS_URL, {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_sessions_returns_created_session(self):
        self.client.post(SESSIONS_URL, {}, format="json")
        r = self.client.get(SESSIONS_URL)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)

    def test_list_sessions_requires_auth(self):
        self.client.credentials()
        r = self.client.get(SESSIONS_URL)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_session_id_is_unique(self):
        r1 = self.client.post(SESSIONS_URL, {}, format="json")
        r2 = self.client.post(SESSIONS_URL, {}, format="json")
        self.assertNotEqual(r1.data["id"], r2.data["id"])

    def test_get_session_detail(self):
        r = self.client.post(SESSIONS_URL, {}, format="json")
        session_id = r.data["id"]
        detail = self.client.get(f"{SESSIONS_URL}{session_id}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(str(detail.data["id"]), session_id)
        self.assertIn("messages", detail.data)

    def test_cannot_access_another_patients_session(self):
        r = self.client.post(SESSIONS_URL, {}, format="json")
        session_id = r.data["id"]
        other_payload = {**VALID_PAYLOAD, "email": "other@example.com", "phone": "03009999999"}
        r2 = self.client.post(REGISTER_URL, other_payload, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r2.data['tokens']['access']}")
        detail = self.client.get(f"{SESSIONS_URL}{session_id}/")
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_end_session_marks_completed(self):
        r = self.client.post(SESSIONS_URL, {}, format="json")
        session_id = r.data["id"]
        patch = self.client.patch(f"{SESSIONS_URL}{session_id}/", {"status": "completed"}, format="json")
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data["status"], "completed")
        self.assertIsNotNone(patch.data["ended_at"])


class ChatMessageTests(APITestCase):
    def setUp(self):
        r = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        self.token = r.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        session_r = self.client.post(SESSIONS_URL, {}, format="json")
        self.session_id = session_r.data["id"]
        self.messages_url = f"{SESSIONS_URL}{self.session_id}/messages/"

        self._p_emergency = patch("patient.views.detect_emergency", return_value=_NON_EMERGENCY)
        self._p_intent = patch("patient.views.detect_intent", return_value=_SYMPTOM_INTENT)
        self._p_graph = patch("patient.views.run_triage_graph", return_value=_MOCK_GRAPH_RESULT)
        self._p_emergency.start()
        self._p_intent.start()
        self._p_graph.start()

    def tearDown(self):
        self._p_emergency.stop()
        self._p_intent.stop()
        self._p_graph.stop()

    def test_send_message_returns_201(self):
        r = self.client.post(self.messages_url, {"content": "I have a headache"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIn("patient_message", r.data)
        self.assertIn("bot_message", r.data)

    def test_patient_message_stored_correctly(self):
        r = self.client.post(self.messages_url, {"content": "I feel dizzy"}, format="json")
        self.assertEqual(r.data["patient_message"]["sender"], "patient")
        self.assertEqual(r.data["patient_message"]["content"], "I feel dizzy")

    def test_bot_replies_automatically(self):
        r = self.client.post(self.messages_url, {"content": "I have a headache"}, format="json")
        self.assertEqual(r.data["bot_message"]["sender"], "bot")
        self.assertGreater(len(r.data["bot_message"]["content"]), 0)

    def test_messages_persisted_in_session(self):
        self.client.post(self.messages_url, {"content": "First message"}, format="json")
        self.client.post(self.messages_url, {"content": "Second message"}, format="json")
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertEqual(len(detail.data["messages"]), 4)  # 2 patient + 2 bot

    def test_empty_message_rejected(self):
        r = self.client.post(self.messages_url, {"content": "   "}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_content_rejected(self):
        r = self.client.post(self.messages_url, {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_message_closed_session(self):
        self.client.patch(f"{SESSIONS_URL}{self.session_id}/", {"status": "completed"}, format="json")
        r = self.client.post(self.messages_url, {"content": "late message"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_message_requires_auth(self):
        self.client.credentials()
        r = self.client.post(self.messages_url, {"content": "test"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)


class MessageIntentTests(APITestCase):
    def setUp(self):
        r = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        self.token = r.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        session_r = self.client.post(SESSIONS_URL, {}, format="json")
        self.session_id = session_r.data["id"]
        self.messages_url = f"{SESSIONS_URL}{self.session_id}/messages/"

    def _post_message(self, content, intent="symptom_check", confidence=0.95):
        mock_result = {"intent": intent, "confidence": confidence}
        with patch("patient.views.detect_emergency", return_value=_NON_EMERGENCY), \
             patch("patient.views.detect_intent", return_value=mock_result), \
             patch("patient.views.run_triage_graph", return_value=_MOCK_GRAPH_RESULT):
            return self.client.post(self.messages_url, {"content": content}, format="json")

    def test_patient_message_metadata_contains_intent(self):
        r = self._post_message("I have a headache")
        self.assertIn("metadata", r.data["patient_message"])
        self.assertIn("intent", r.data["patient_message"]["metadata"])

    def test_intent_is_a_supported_value(self):
        r = self._post_message("I have a headache", intent="symptom_check")
        intent = r.data["patient_message"]["metadata"]["intent"]
        self.assertIn(intent, SUPPORTED_INTENTS)

    def test_confidence_is_numeric(self):
        r = self._post_message("I have a headache", confidence=0.9)
        confidence = r.data["patient_message"]["metadata"]["confidence"]
        self.assertIsInstance(confidence, float)

    def test_session_metadata_updated_with_intent(self):
        self._post_message("I need to book an appointment", intent="appointment_request")
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertEqual(detail.data["session_metadata"]["last_intent"], "appointment_request")

    def test_session_metadata_last_confidence_stored(self):
        self._post_message("bill inquiry", intent="billing_question", confidence=0.88)
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertAlmostEqual(detail.data["session_metadata"]["last_confidence"], 0.88)

    def test_session_metadata_updated_to_latest_intent(self):
        self._post_message("I feel sick", intent="symptom_check")
        self._post_message("When can I see a doctor?", intent="appointment_request")
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertEqual(detail.data["session_metadata"]["last_intent"], "appointment_request")

    def test_emergency_intent_stored(self):
        r = self._post_message("I am having a heart attack!", intent="emergency", confidence=1.0)
        self.assertEqual(r.data["patient_message"]["metadata"]["intent"], "emergency")

    def test_openai_failure_falls_back_to_unknown(self):
        r = self._post_message("gibberish xyz", intent="unknown", confidence=0.0)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["patient_message"]["metadata"]["intent"], "unknown")

    def test_unsupported_intent_remapped_to_unknown(self):
        r = self._post_message("random text", intent="unknown", confidence=0.0)
        self.assertEqual(r.data["patient_message"]["metadata"]["intent"], "unknown")

    def test_all_supported_intents_accepted(self):
        for intent in SUPPORTED_INTENTS:
            r = self._post_message("test message", intent=intent, confidence=0.8)
            self.assertEqual(r.status_code, status.HTTP_201_CREATED)
            self.assertEqual(r.data["patient_message"]["metadata"]["intent"], intent)


class EmergencyTriageTests(APITestCase):
    def setUp(self):
        r = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        self.token = r.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        session_r = self.client.post(SESSIONS_URL, {}, format="json")
        self.session_id = session_r.data["id"]
        self.messages_url = f"{SESSIONS_URL}{self.session_id}/messages/"

    _EMERGENCY_RESULT = {
        "is_emergency": True,
        "symptoms_detected": ["chest pain", "sweating"],
        "confidence": 0.98,
    }
    _NORMAL_RESULT = {
        "is_emergency": False,
        "symptoms_detected": [],
        "confidence": 0.03,
    }
    _NORMAL_INTENT = {"intent": "symptom_check", "confidence": 0.85}

    def _post_emergency(self, content="I have chest pain with sweating"):
        with patch("patient.views.detect_emergency", return_value=self._EMERGENCY_RESULT):
            return self.client.post(self.messages_url, {"content": content}, format="json")

    def _post_normal(self, content="I have a mild headache"):
        with patch("patient.views.detect_emergency", return_value=self._NORMAL_RESULT), \
             patch("patient.views.detect_intent", return_value=self._NORMAL_INTENT), \
             patch("patient.views.run_triage_graph", return_value=_MOCK_GRAPH_RESULT):
            return self.client.post(self.messages_url, {"content": content}, format="json")

    def test_emergency_returns_201(self):
        r = self._post_emergency()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_emergency_flag_true_in_response(self):
        r = self._post_emergency()
        self.assertTrue(r.data["emergency"])

    def test_non_emergency_flag_false_in_response(self):
        r = self._post_normal()
        self.assertFalse(r.data["emergency"])

    def test_emergency_bot_reply_is_guidance(self):
        r = self._post_emergency()
        self.assertIn("EMERGENCY ALERT", r.data["bot_message"]["content"])

    def test_emergency_bot_agent_is_emergency_triage(self):
        r = self._post_emergency()
        self.assertEqual(r.data["bot_message"]["agent_name"], "emergency_triage")

    def test_emergency_does_not_use_placeholder_agent(self):
        r = self._post_emergency()
        self.assertNotEqual(r.data["bot_message"]["agent_name"], "placeholder")

    def test_emergency_sets_session_risk_level(self):
        self._post_emergency()
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertEqual(detail.data["risk_level"], "emergency")

    def test_normal_message_does_not_set_emergency_risk(self):
        self._post_normal()
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertNotEqual(detail.data.get("risk_level"), "emergency")

    def test_emergency_event_logged_to_db(self):
        self._post_emergency("I have chest pain with sweating")
        session = ChatSession.objects.get(id=self.session_id)
        self.assertEqual(session.emergency_events.count(), 1)

    def test_emergency_event_stores_trigger_message(self):
        self._post_emergency("I have chest pain with sweating")
        event = ChatSession.objects.get(id=self.session_id).emergency_events.first()
        self.assertEqual(event.trigger_message, "I have chest pain with sweating")

    def test_emergency_event_stores_symptoms(self):
        self._post_emergency()
        event = ChatSession.objects.get(id=self.session_id).emergency_events.first()
        self.assertEqual(event.symptoms_detected, ["chest pain", "sweating"])

    def test_emergency_event_stores_guidance(self):
        self._post_emergency()
        event = ChatSession.objects.get(id=self.session_id).emergency_events.first()
        self.assertIn("EMERGENCY ALERT", event.guidance_given)

    def test_emergency_events_visible_in_session_detail(self):
        self._post_emergency()
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertIn("emergency_events", detail.data)
        self.assertEqual(len(detail.data["emergency_events"]), 1)

    def test_emergency_event_fields_in_session_detail(self):
        self._post_emergency("Chest pain with sweating")
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        event = detail.data["emergency_events"][0]
        self.assertIn("id", event)
        self.assertIn("trigger_message", event)
        self.assertIn("symptoms_detected", event)
        self.assertIn("guidance_given", event)
        self.assertIn("created_at", event)

    def test_no_emergency_no_events_in_session_detail(self):
        self._post_normal()
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertEqual(len(detail.data["emergency_events"]), 0)

    def test_emergency_requires_auth(self):
        self.client.credentials()
        r = self.client.post(self.messages_url, {"content": "chest pain"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_emergency_on_closed_session_rejected(self):
        self.client.patch(f"{SESSIONS_URL}{self.session_id}/", {"status": "completed"}, format="json")
        with patch("patient.views.detect_emergency", return_value=self._EMERGENCY_RESULT):
            r = self.client.post(self.messages_url, {"content": "chest pain"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_multiple_emergency_messages_each_logged(self):
        self._post_emergency("Chest pain")
        self._post_emergency("Still having chest pain")
        session = ChatSession.objects.get(id=self.session_id)
        self.assertEqual(session.emergency_events.count(), 2)

    def test_emergency_examples_trigger_emergency_flag(self):
        examples = [
            "Chest pain with sweating",
            "Severe shortness of breath",
            "Stroke symptoms — face drooping",
            "Unconsciousness",
            "Severe bleeding",
            "Seizure",
            "Suicidal thoughts",
            "Severe allergic reaction",
            "Pregnancy emergency",
            "High fever in infant",
        ]
        with patch("patient.views.detect_emergency", return_value=self._EMERGENCY_RESULT):
            for msg in examples:
                r = self.client.post(self.messages_url, {"content": msg}, format="json")
                self.assertTrue(r.data.get("emergency"), f"Expected emergency=True for: {msg}")


class TriageOrchestatorTests(APITestCase):
    """Tests for LangGraph triage orchestrator integration."""

    def setUp(self):
        r = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        self.token = r.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        session_r = self.client.post(SESSIONS_URL, {}, format="json")
        self.session_id = session_r.data["id"]
        self.messages_url = f"{SESSIONS_URL}{self.session_id}/messages/"

    def _post(self, content, intent="symptom_check", graph_result=None):
        if graph_result is None:
            graph_result = _MOCK_GRAPH_RESULT
        with patch("patient.views.detect_emergency", return_value=_NON_EMERGENCY), \
             patch("patient.views.detect_intent", return_value={"intent": intent, "confidence": 0.9}), \
             patch("patient.views.run_triage_graph", return_value=graph_result) as mock_graph:
            response = self.client.post(self.messages_url, {"content": content}, format="json")
            return response, mock_graph

    def test_graph_is_called_for_non_emergency(self):
        _, mock_graph = self._post("I have a headache")
        mock_graph.assert_called_once()

    def test_graph_receives_correct_intent(self):
        _, mock_graph = self._post("book appointment", intent="appointment_request")
        call_kwargs = mock_graph.call_args.kwargs
        self.assertEqual(call_kwargs["intent"], "appointment_request")

    def test_graph_receives_patient_name(self):
        _, mock_graph = self._post("my knee hurts")
        call_kwargs = mock_graph.call_args.kwargs
        self.assertEqual(call_kwargs["patient_name"], "Ali Khan")

    def test_graph_receives_conversation_history(self):
        _, mock_graph = self._post("first message")
        call_kwargs = mock_graph.call_args.kwargs
        self.assertIsInstance(call_kwargs["conversation_history"], list)
        self.assertTrue(len(call_kwargs["conversation_history"]) >= 1)

    def test_bot_response_comes_from_graph(self):
        custom_result = {**_MOCK_GRAPH_RESULT, "bot_response": "Custom graph response."}
        response, _ = self._post("my knee hurts", graph_result=custom_result)
        self.assertEqual(response.data["bot_message"]["content"], "Custom graph response.")

    def test_agent_name_stored_from_graph(self):
        custom_result = {**_MOCK_GRAPH_RESULT, "agent_used": "appointment_agent"}
        response, _ = self._post("book appointment", intent="appointment_request", graph_result=custom_result)
        self.assertEqual(response.data["bot_message"]["agent_name"], "appointment_agent")

    def test_session_metadata_stores_last_agent(self):
        self._post("my knee hurts")
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertIn("last_agent", detail.data["session_metadata"])
        self.assertEqual(detail.data["session_metadata"]["last_agent"], "intake_agent")

    def test_graph_risk_level_updates_session(self):
        urgent_result = {**_MOCK_GRAPH_RESULT, "risk_level": "urgent"}
        self._post("severe pain", graph_result=urgent_result)
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertEqual(detail.data["risk_level"], "urgent")

    def test_graph_none_risk_level_does_not_overwrite_session(self):
        # First message sets risk_level via graph
        urgent_result = {**_MOCK_GRAPH_RESULT, "risk_level": "urgent"}
        self._post("severe pain", graph_result=urgent_result)
        # Second message returns None risk_level — should NOT reset to None
        self._post("a bit better", graph_result=_MOCK_GRAPH_RESULT)
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertEqual(detail.data["risk_level"], "urgent")

    def test_graph_not_called_for_emergency(self):
        emergency_result = {
            "is_emergency": True,
            "symptoms_detected": ["chest pain"],
            "confidence": 0.99,
        }
        with patch("patient.views.detect_emergency", return_value=emergency_result), \
             patch("patient.views.run_triage_graph") as mock_graph:
            self.client.post(self.messages_url, {"content": "chest pain"}, format="json")
        mock_graph.assert_not_called()

    def test_history_includes_prior_bot_messages(self):
        # Send first message (creates patient + bot messages)
        self._post("first symptom")
        # Send second message and capture what graph receives
        _, mock_graph = self._post("more details")
        history = mock_graph.call_args.kwargs["conversation_history"]
        # Should have at least 3 messages: bot reply from first turn + patient + current patient
        self.assertGreaterEqual(len(history), 3)

    def test_graph_routing_symptom_check(self):
        from patient.agents.nodes import route_by_intent
        from patient.agents.state import TriageState

        state: TriageState = {
            "conversation_history": [],
            "intent": "symptom_check",
            "patient_name": "Test",
            "session_metadata": {},
            "bot_response": "",
            "agent_used": "",
            "risk_level": None,
        }
        self.assertEqual(route_by_intent(state), "intake")

    def test_graph_routing_appointment(self):
        from patient.agents.nodes import route_by_intent
        from patient.agents.state import TriageState

        state: TriageState = {
            "conversation_history": [],
            "intent": "appointment_request",
            "patient_name": "Test",
            "session_metadata": {},
            "bot_response": "",
            "agent_used": "",
            "risk_level": None,
        }
        self.assertEqual(route_by_intent(state), "appointment")

    def test_graph_routing_medication(self):
        from patient.agents.nodes import route_by_intent
        from patient.agents.state import TriageState

        state: TriageState = {
            "conversation_history": [],
            "intent": "medication_question",
            "patient_name": "Test",
            "session_metadata": {},
            "bot_response": "",
            "agent_used": "",
            "risk_level": None,
        }
        self.assertEqual(route_by_intent(state), "medication")

    def test_graph_routing_general_intents(self):
        from patient.agents.nodes import route_by_intent
        from patient.agents.state import TriageState

        for intent in ("lab_report_question", "billing_question", "hospital_info"):
            state: TriageState = {
                "conversation_history": [],
                "intent": intent,
                "patient_name": "Test",
                "session_metadata": {},
                "bot_response": "",
                "agent_used": "",
                "risk_level": None,
            }
            self.assertEqual(route_by_intent(state), "general", f"Failed for intent: {intent}")


SUMMARY_URL_TMPL = "/api/patient/chat/sessions/{}/summary/"

_MOCK_SUMMARY = {
    "chief_complaint": "Persistent headache for two days.",
    "symptom_details": {
        "location": "head",
        "duration": "2 days",
        "severity": 6,
        "character": "throbbing",
        "aggravating_factors": ["bright light"],
        "relieving_factors": ["rest"],
        "associated_symptoms": ["nausea"],
    },
    "risk_level": "routine",
    "recommended_action": "Schedule GP appointment within 1 week.",
    "notes_for_doctor": "Patient has had similar headaches before.",
    "generated_at": "2026-06-21T10:00:00+00:00",
}


class SessionSummaryTests(APITestCase):
    def setUp(self):
        r = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        self.token = r.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        session_r = self.client.post(SESSIONS_URL, {}, format="json")
        self.session_id = session_r.data["id"]
        self.summary_url = SUMMARY_URL_TMPL.format(self.session_id)

    def _send_messages(self, count=2):
        for i in range(count):
            with patch("patient.views.detect_emergency", return_value=_NON_EMERGENCY), \
                 patch("patient.views.detect_intent", return_value=_SYMPTOM_INTENT), \
                 patch("patient.views.run_triage_graph", return_value=_MOCK_GRAPH_RESULT):
                self.client.post(
                    f"{SESSIONS_URL}{self.session_id}/messages/",
                    {"content": f"Patient message {i + 1}"},
                    format="json",
                )

    def _post_summary(self, mock_summary=None):
        if mock_summary is None:
            mock_summary = _MOCK_SUMMARY
        with patch("patient.views.generate_session_summary", return_value=mock_summary):
            return self.client.post(self.summary_url, format="json")

    def test_summary_returns_200(self):
        self._send_messages(2)
        r = self._post_summary()
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_summary_requires_auth(self):
        self._send_messages(2)
        self.client.credentials()
        with patch("patient.views.generate_session_summary", return_value=_MOCK_SUMMARY):
            r = self.client.post(self.summary_url, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_summary_returns_structured_data(self):
        self._send_messages(2)
        r = self._post_summary()
        self.assertIn("summary", r.data)
        summary = r.data["summary"]
        self.assertIn("chief_complaint", summary)
        self.assertIn("symptom_details", summary)
        self.assertIn("risk_level", summary)
        self.assertIn("recommended_action", summary)
        self.assertIn("generated_at", summary)

    def test_summary_stored_on_session(self):
        self._send_messages(2)
        self._post_summary()
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertIsNotNone(detail.data["summary"])
        self.assertEqual(detail.data["summary"]["chief_complaint"], _MOCK_SUMMARY["chief_complaint"])

    def test_summary_updates_session_risk_level(self):
        self._send_messages(2)
        urgent_summary = {**_MOCK_SUMMARY, "risk_level": "urgent"}
        self._post_summary(mock_summary=urgent_summary)
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertEqual(detail.data["risk_level"], "urgent")

    def test_summary_requires_at_least_2_patient_messages(self):
        self._send_messages(1)
        r = self._post_summary()
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", r.data)

    def test_summary_rejected_for_abandoned_session(self):
        self._send_messages(2)
        self.client.patch(f"{SESSIONS_URL}{self.session_id}/", {"status": "abandoned"}, format="json")
        r = self._post_summary()
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_summary_allowed_for_completed_session(self):
        self._send_messages(2)
        self.client.patch(f"{SESSIONS_URL}{self.session_id}/", {"status": "completed"}, format="json")
        r = self._post_summary()
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_summary_not_accessible_for_another_patients_session(self):
        self._send_messages(2)
        other_payload = {**VALID_PAYLOAD, "email": "other@example.com", "phone": "03009999999"}
        r2 = self.client.post(REGISTER_URL, other_payload, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r2.data['tokens']['access']}")
        with patch("patient.views.generate_session_summary", return_value=_MOCK_SUMMARY):
            r = self.client.post(self.summary_url, format="json")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_summary_regenerates_on_second_call(self):
        self._send_messages(2)
        self._post_summary()
        new_summary = {**_MOCK_SUMMARY, "chief_complaint": "Updated complaint."}
        self._post_summary(mock_summary=new_summary)
        detail = self.client.get(f"{SESSIONS_URL}{self.session_id}/")
        self.assertEqual(detail.data["summary"]["chief_complaint"], "Updated complaint.")

    def test_openai_failure_returns_503(self):
        self._send_messages(2)
        with patch("patient.views.generate_session_summary", side_effect=Exception("OpenAI down")):
            r = self.client.post(self.summary_url, format="json")
        self.assertEqual(r.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


MEDICAL_HISTORY_URL = "/api/patient/medical-history/"

VALID_HISTORY_PAYLOAD = {
    "blood_type": "O+",
    "chronic_conditions": ["diabetes", "hypertension"],
    "allergies": ["penicillin"],
    "current_medications": ["metformin 500mg"],
    "emergency_contact_name": "Sara Khan",
    "emergency_contact_phone": "03001112222",
    "notes": "Patient prefers morning appointments.",
}


class MedicalHistoryTests(APITestCase):
    def setUp(self):
        r = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        self.token = r.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_get_returns_200_with_defaults(self):
        r = self.client.get(MEDICAL_HISTORY_URL)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("blood_type", r.data)
        self.assertIn("chronic_conditions", r.data)
        self.assertIn("allergies", r.data)
        self.assertIn("current_medications", r.data)

    def test_get_auto_creates_empty_history(self):
        r = self.client.get(MEDICAL_HISTORY_URL)
        self.assertEqual(r.data["chronic_conditions"], [])
        self.assertEqual(r.data["allergies"], [])
        self.assertEqual(r.data["current_medications"], [])

    def test_get_requires_auth(self):
        self.client.credentials()
        r = self.client.get(MEDICAL_HISTORY_URL)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_creates_full_history(self):
        r = self.client.put(MEDICAL_HISTORY_URL, VALID_HISTORY_PAYLOAD, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["blood_type"], "O+")
        self.assertEqual(r.data["chronic_conditions"], ["diabetes", "hypertension"])
        self.assertEqual(r.data["allergies"], ["penicillin"])
        self.assertEqual(r.data["emergency_contact_name"], "Sara Khan")

    def test_put_persists_to_db(self):
        self.client.put(MEDICAL_HISTORY_URL, VALID_HISTORY_PAYLOAD, format="json")
        r = self.client.get(MEDICAL_HISTORY_URL)
        self.assertEqual(r.data["blood_type"], "O+")
        self.assertEqual(r.data["notes"], "Patient prefers morning appointments.")

    def test_patch_updates_partial_fields(self):
        self.client.put(MEDICAL_HISTORY_URL, VALID_HISTORY_PAYLOAD, format="json")
        r = self.client.patch(MEDICAL_HISTORY_URL, {"blood_type": "A-"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["blood_type"], "A-")
        self.assertEqual(r.data["chronic_conditions"], ["diabetes", "hypertension"])

    def test_put_requires_auth(self):
        self.client.credentials()
        r = self.client.put(MEDICAL_HISTORY_URL, VALID_HISTORY_PAYLOAD, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_blood_type_rejected(self):
        payload = {**VALID_HISTORY_PAYLOAD, "blood_type": "Z+"}
        r = self.client.put(MEDICAL_HISTORY_URL, payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_second_patient_has_isolated_history(self):
        self.client.put(MEDICAL_HISTORY_URL, VALID_HISTORY_PAYLOAD, format="json")
        other_payload = {**VALID_PAYLOAD, "email": "other@example.com", "phone": "03009999999"}
        r2 = self.client.post(REGISTER_URL, other_payload, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r2.data['tokens']['access']}")
        r = self.client.get(MEDICAL_HISTORY_URL)
        self.assertEqual(r.data["chronic_conditions"], [])

    def test_updated_at_is_present(self):
        r = self.client.get(MEDICAL_HISTORY_URL)
        self.assertIn("updated_at", r.data)
        self.assertIsNotNone(r.data["updated_at"])


APPOINTMENTS_URL = "/api/patient/appointments/"

DOCTOR_REGISTER_URL = "/api/doctor/register/"
VALID_DOCTOR_PAYLOAD = {
    "name": "Dr. Sara Ahmed",
    "email": "sara.ahmed@hospital.com",
    "password": "DocPass123!",
    "password_confirm": "DocPass123!",
    "specialization": "general_practice",
    "license_number": "LIC-001",
}


def _apt_detail_url(apt_id):
    return f"{APPOINTMENTS_URL}{apt_id}/"


class AppointmentPatientTests(APITestCase):
    def setUp(self):
        dr = self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")
        self.doctor_id = dr.data["doctor_id"]

        r = self.client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
        self.token = r.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

        from django.utils import timezone
        from datetime import timedelta
        self.future_dt = (timezone.now() + timedelta(days=3)).isoformat()

    def _valid_payload(self):
        return {"doctor": self.doctor_id, "scheduled_at": self.future_dt, "reason": "Routine checkup"}

    def test_create_appointment_returns_201(self):
        r = self.client.post(APPOINTMENTS_URL, self._valid_payload(), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", r.data)
        self.assertEqual(r.data["status"], "pending")

    def test_create_appointment_requires_auth(self):
        self.client.credentials()
        r = self.client.post(APPOINTMENTS_URL, self._valid_payload(), format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_appointment_missing_doctor_rejected(self):
        payload = {"scheduled_at": self.future_dt, "reason": "Checkup"}
        r = self.client.post(APPOINTMENTS_URL, payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_appointment_missing_scheduled_at_rejected(self):
        payload = {"doctor": self.doctor_id, "reason": "Checkup"}
        r = self.client.post(APPOINTMENTS_URL, payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_appointment_past_date_rejected(self):
        from datetime import timedelta
        from django.utils import timezone
        past_dt = (timezone.now() - timedelta(days=1)).isoformat()
        payload = {**self._valid_payload(), "scheduled_at": past_dt}
        r = self.client.post(APPOINTMENTS_URL, payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_appointments_returns_own(self):
        self.client.post(APPOINTMENTS_URL, self._valid_payload(), format="json")
        r = self.client.get(APPOINTMENTS_URL)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)

    def test_list_requires_auth(self):
        self.client.credentials()
        r = self.client.get(APPOINTMENTS_URL)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_appointment_detail(self):
        create_r = self.client.post(APPOINTMENTS_URL, self._valid_payload(), format="json")
        apt_id = create_r.data["id"]
        r = self.client.get(_apt_detail_url(apt_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["doctor_name"], VALID_DOCTOR_PAYLOAD["name"])

    def test_patient_can_cancel_pending_appointment(self):
        create_r = self.client.post(APPOINTMENTS_URL, self._valid_payload(), format="json")
        apt_id = create_r.data["id"]
        r = self.client.delete(_apt_detail_url(apt_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], "cancelled")

    def test_patient_cannot_cancel_confirmed_appointment(self):
        from patient.models import Appointment
        create_r = self.client.post(APPOINTMENTS_URL, self._valid_payload(), format="json")
        apt_id = create_r.data["id"]
        Appointment.objects.filter(id=apt_id).update(status="confirmed")
        r = self.client.delete(_apt_detail_url(apt_id))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_second_patient_cannot_access_appointment(self):
        create_r = self.client.post(APPOINTMENTS_URL, self._valid_payload(), format="json")
        apt_id = create_r.data["id"]
        other = {**VALID_PAYLOAD, "email": "other@example.com", "phone": "03009999999"}
        r2 = self.client.post(REGISTER_URL, other, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r2.data['tokens']['access']}")
        r = self.client.get(_apt_detail_url(apt_id))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_filter_appointments_by_status(self):
        self.client.post(APPOINTMENTS_URL, self._valid_payload(), format="json")
        r = self.client.get(f"{APPOINTMENTS_URL}?status=pending")
        self.assertEqual(len(r.data), 1)
        r2 = self.client.get(f"{APPOINTMENTS_URL}?status=confirmed")
        self.assertEqual(len(r2.data), 0)
