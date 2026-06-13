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
        non_emergency = {"is_emergency": False, "symptoms_detected": [], "confidence": 0.0}
        with patch("patient.views.detect_emergency", return_value=non_emergency):
            with patch("patient.views.detect_intent", return_value=mock_result):
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
        with patch("patient.views.detect_intent", return_value={"intent": "unknown", "confidence": 0.0}):
            r = self.client.post(self.messages_url, {"content": "gibberish xyz"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["patient_message"]["metadata"]["intent"], "unknown")

    def test_unsupported_intent_remapped_to_unknown(self):
        with patch("patient.views.detect_intent", return_value={"intent": "unknown", "confidence": 0.0}):
            r = self.client.post(self.messages_url, {"content": "random text"}, format="json")
        self.assertEqual(r.data["patient_message"]["metadata"]["intent"], "unknown")

    def test_all_supported_intents_accepted(self):
        for intent in SUPPORTED_INTENTS:
            mock_result = {"intent": intent, "confidence": 0.8}
            with patch("patient.views.detect_intent", return_value=mock_result):
                r = self.client.post(self.messages_url, {"content": "test message"}, format="json")
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
        with patch("patient.views.detect_emergency", return_value=self._NORMAL_RESULT):
            with patch("patient.views.detect_intent", return_value=self._NORMAL_INTENT):
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
        for msg in examples:
            with patch("patient.views.detect_emergency", return_value=self._EMERGENCY_RESULT):
                r = self.client.post(self.messages_url, {"content": msg}, format="json")
            self.assertTrue(r.data.get("emergency"), f"Expected emergency=True for: {msg}")
