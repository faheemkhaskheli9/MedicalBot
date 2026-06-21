from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from patient.models import ChatSession

DOCTOR_REGISTER_URL = "/api/doctor/register/"
DOCTOR_LOGIN_URL = "/api/doctor/login/"
DOCTOR_PROFILE_URL = "/api/doctor/profile/"
DOCTOR_SESSIONS_URL = "/api/doctor/patients/sessions/"

PATIENT_REGISTER_URL = "/api/patient/register/"
PATIENT_SESSIONS_URL = "/api/patient/chat/sessions/"

VALID_DOCTOR_PAYLOAD = {
    "name": "Dr. Sara Ahmed",
    "email": "sara.ahmed@hospital.com",
    "password": "DocPass123!",
    "password_confirm": "DocPass123!",
    "specialization": "general_practice",
    "license_number": "LIC-001",
}

VALID_PATIENT_PAYLOAD = {
    "name": "Ali Khan",
    "age": 30,
    "gender": "male",
    "phone": "03001234567",
    "email": "ali@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!",
}

_NON_EMERGENCY = {"is_emergency": False, "symptoms_detected": [], "confidence": 0.0}
_SYMPTOM_INTENT = {"intent": "symptom_check", "confidence": 0.9}
_MOCK_GRAPH_RESULT = {
    "bot_response": "Tell me more.",
    "agent_used": "intake_agent",
    "risk_level": None,
}


class DoctorRegistrationTests(APITestCase):
    def test_register_success(self):
        r = self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIn("doctor_id", r.data)
        self.assertIn("tokens", r.data)
        self.assertIn("access", r.data["tokens"])

    def test_duplicate_email_rejected(self):
        self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")
        payload = {**VALID_DOCTOR_PAYLOAD, "license_number": "LIC-002"}
        r = self.client.post(DOCTOR_REGISTER_URL, payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_license_rejected(self):
        self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")
        payload = {**VALID_DOCTOR_PAYLOAD, "email": "other@hospital.com"}
        r = self.client.post(DOCTOR_REGISTER_URL, payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_mismatch_rejected(self):
        payload = {**VALID_DOCTOR_PAYLOAD, "password_confirm": "WrongPass!"}
        r = self.client.post(DOCTOR_REGISTER_URL, payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_license_rejected(self):
        payload = {k: v for k, v in VALID_DOCTOR_PAYLOAD.items() if k != "license_number"}
        r = self.client.post(DOCTOR_REGISTER_URL, payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_not_returned(self):
        r = self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")
        self.assertNotIn("password", r.data)

    def test_patient_email_cannot_register_as_doctor(self):
        self.client.post(PATIENT_REGISTER_URL, VALID_PATIENT_PAYLOAD, format="json")
        payload = {**VALID_DOCTOR_PAYLOAD, "email": VALID_PATIENT_PAYLOAD["email"]}
        r = self.client.post(DOCTOR_REGISTER_URL, payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class DoctorLoginTests(APITestCase):
    def setUp(self):
        self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")

    def test_login_success(self):
        r = self.client.post(
            DOCTOR_LOGIN_URL,
            {"email": VALID_DOCTOR_PAYLOAD["email"], "password": VALID_DOCTOR_PAYLOAD["password"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("access", r.data["tokens"])

    def test_wrong_password_rejected(self):
        r = self.client.post(
            DOCTOR_LOGIN_URL,
            {"email": VALID_DOCTOR_PAYLOAD["email"], "password": "BadPass!"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patient_cannot_login_as_doctor(self):
        self.client.post(PATIENT_REGISTER_URL, VALID_PATIENT_PAYLOAD, format="json")
        r = self.client.post(
            DOCTOR_LOGIN_URL,
            {"email": VALID_PATIENT_PAYLOAD["email"], "password": VALID_PATIENT_PAYLOAD["password"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class DoctorProfileTests(APITestCase):
    def setUp(self):
        r = self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")
        self.token = r.data["tokens"]["access"]

    def test_profile_requires_auth(self):
        r = self.client.get(DOCTOR_PROFILE_URL)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_profile_returns_data(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        r = self.client.get(DOCTOR_PROFILE_URL)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["name"], "Dr. Sara Ahmed")
        self.assertEqual(r.data["email"], "sara.ahmed@hospital.com")
        self.assertEqual(r.data["specialization"], "general_practice")
        self.assertIn("license_number", r.data)

    def test_patient_token_denied_doctor_profile(self):
        patient_r = self.client.post(PATIENT_REGISTER_URL, VALID_PATIENT_PAYLOAD, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {patient_r.data['tokens']['access']}")
        r = self.client.get(DOCTOR_PROFILE_URL)
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


class DoctorPatientSessionTests(APITestCase):
    def setUp(self):
        dr = self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")
        self.doctor_token = dr.data["tokens"]["access"]

        pr = self.client.post(PATIENT_REGISTER_URL, VALID_PATIENT_PAYLOAD, format="json")
        self.patient_token = pr.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")
        sr = self.client.post(PATIENT_SESSIONS_URL, {}, format="json")
        self.session_id = sr.data["id"]

        for _ in range(2):
            with patch("patient.views.detect_emergency", return_value=_NON_EMERGENCY), \
                 patch("patient.views.detect_intent", return_value=_SYMPTOM_INTENT), \
                 patch("patient.views.run_triage_graph", return_value=_MOCK_GRAPH_RESULT):
                self.client.post(
                    f"{PATIENT_SESSIONS_URL}{self.session_id}/messages/",
                    {"content": "I have a headache"},
                    format="json",
                )

    def test_doctor_can_list_sessions(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")
        r = self.client.get(DOCTOR_SESSIONS_URL)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)

    def test_session_list_requires_auth(self):
        self.client.credentials()
        r = self.client.get(DOCTOR_SESSIONS_URL)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_cannot_access_doctor_sessions(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")
        r = self.client.get(DOCTOR_SESSIONS_URL)
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_session_list_contains_patient_info(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")
        r = self.client.get(DOCTOR_SESSIONS_URL)
        session = r.data[0]
        self.assertIn("patient_name", session)
        self.assertIn("patient_age", session)
        self.assertIn("risk_level", session)
        self.assertIn("message_count", session)
        self.assertIn("has_summary", session)

    def test_doctor_can_get_session_detail(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")
        r = self.client.get(f"{DOCTOR_SESSIONS_URL}{self.session_id}/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("messages", r.data)
        self.assertIn("summary", r.data)

    def test_session_detail_includes_transcript(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")
        r = self.client.get(f"{DOCTOR_SESSIONS_URL}{self.session_id}/")
        self.assertGreater(len(r.data["messages"]), 0)
        first_msg = r.data["messages"][0]
        self.assertIn("sender", first_msg)
        self.assertIn("content", first_msg)

    def test_session_detail_includes_patient_demographics(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")
        r = self.client.get(f"{DOCTOR_SESSIONS_URL}{self.session_id}/")
        self.assertEqual(r.data["patient_name"], "Ali Khan")
        self.assertEqual(r.data["patient_age"], 30)
        self.assertIn("patient_gender", r.data)
        self.assertIn("patient_phone", r.data)

    def test_filter_sessions_by_risk_level(self):
        session = ChatSession.objects.get(id=self.session_id)
        session.risk_level = "urgent"
        session.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")
        r = self.client.get(f"{DOCTOR_SESSIONS_URL}?risk_level=urgent")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)

        r2 = self.client.get(f"{DOCTOR_SESSIONS_URL}?risk_level=emergency")
        self.assertEqual(len(r2.data), 0)

    def test_filter_sessions_by_status(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")
        self.client.patch(
            f"{PATIENT_SESSIONS_URL}{self.session_id}/",
            {"status": "completed"},
            format="json",
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")
        r = self.client.get(f"{DOCTOR_SESSIONS_URL}?status=completed")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)

        r2 = self.client.get(f"{DOCTOR_SESSIONS_URL}?status=active")
        self.assertEqual(len(r2.data), 0)

    def test_unknown_session_returns_404(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")
        r = self.client.get(f"{DOCTOR_SESSIONS_URL}00000000-0000-0000-0000-000000000000/")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
