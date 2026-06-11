from rest_framework import status
from rest_framework.test import APITestCase

from .models import ChatSession, Patient

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
