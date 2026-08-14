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

def _notes_url(session_id):
    return f"/api/doctor/patients/sessions/{session_id}/notes/"

def _note_detail_url(session_id, note_id):
    return f"/api/doctor/patients/sessions/{session_id}/notes/{note_id}/"

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


class DoctorNoteTests(APITestCase):
    def setUp(self):
        dr = self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")
        self.doctor_token = dr.data["tokens"]["access"]

        second_doctor_payload = {
            **VALID_DOCTOR_PAYLOAD,
            "email": "other.doc@hospital.com",
            "license_number": "LIC-999",
        }
        dr2 = self.client.post(DOCTOR_REGISTER_URL, second_doctor_payload, format="json")
        self.other_doctor_token = dr2.data["tokens"]["access"]

        pr = self.client.post(PATIENT_REGISTER_URL, VALID_PATIENT_PAYLOAD, format="json")
        self.patient_token = pr.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")
        sr = self.client.post(PATIENT_SESSIONS_URL, {}, format="json")
        self.session_id = sr.data["id"]

    def _auth_doctor(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")

    def _auth_other_doctor(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.other_doctor_token}")

    def _auth_patient(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")

    # --- list / create ---

    def test_create_note_success(self):
        self._auth_doctor()
        r = self.client.post(_notes_url(self.session_id), {"note": "Patient seems anxious."}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["note"], "Patient seems anxious.")
        self.assertIn("id", r.data)
        self.assertIn("doctor_name", r.data)

    def test_list_notes_success(self):
        self._auth_doctor()
        self.client.post(_notes_url(self.session_id), {"note": "First note."}, format="json")
        self.client.post(_notes_url(self.session_id), {"note": "Second note."}, format="json")
        r = self.client.get(_notes_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 2)

    def test_notes_require_auth(self):
        self.client.credentials()
        r = self.client.get(_notes_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_cannot_create_note(self):
        self._auth_patient()
        r = self.client.post(_notes_url(self.session_id), {"note": "Self note."}, format="json")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_note_empty_content_rejected(self):
        self._auth_doctor()
        r = self.client.post(_notes_url(self.session_id), {"note": ""}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_note_unknown_session_returns_404(self):
        self._auth_doctor()
        r = self.client.post(
            _notes_url("00000000-0000-0000-0000-000000000000"),
            {"note": "Some note."},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    # --- detail ---

    def test_get_note_detail(self):
        self._auth_doctor()
        create_r = self.client.post(_notes_url(self.session_id), {"note": "Detail note."}, format="json")
        note_id = create_r.data["id"]
        r = self.client.get(_note_detail_url(self.session_id, note_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["note"], "Detail note.")

    def test_delete_own_note(self):
        self._auth_doctor()
        create_r = self.client.post(_notes_url(self.session_id), {"note": "To delete."}, format="json")
        note_id = create_r.data["id"]
        r = self.client.delete(_note_detail_url(self.session_id, note_id))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        # confirm it is gone
        r2 = self.client.get(_note_detail_url(self.session_id, note_id))
        self.assertEqual(r2.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_doctor_cannot_delete_note(self):
        self._auth_doctor()
        create_r = self.client.post(_notes_url(self.session_id), {"note": "Protected note."}, format="json")
        note_id = create_r.data["id"]

        self._auth_other_doctor()
        r = self.client.delete(_note_detail_url(self.session_id, note_id))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_doctor_can_read_note(self):
        self._auth_doctor()
        create_r = self.client.post(_notes_url(self.session_id), {"note": "Readable note."}, format="json")
        note_id = create_r.data["id"]

        self._auth_other_doctor()
        r = self.client.get(_note_detail_url(self.session_id, note_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_note_detail_unknown_note_returns_404(self):
        self._auth_doctor()
        r = self.client.get(_note_detail_url(self.session_id, "00000000-0000-0000-0000-000000000000"))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


def _assign_url(session_id):
    return f"/api/doctor/patients/sessions/{session_id}/assign/"


class SessionAssignTests(APITestCase):
    def setUp(self):
        dr = self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")
        self.doctor_token = dr.data["tokens"]["access"]

        second_doctor_payload = {
            **VALID_DOCTOR_PAYLOAD,
            "email": "other.doc@hospital.com",
            "license_number": "LIC-999",
        }
        dr2 = self.client.post(DOCTOR_REGISTER_URL, second_doctor_payload, format="json")
        self.other_doctor_token = dr2.data["tokens"]["access"]

        pr = self.client.post(PATIENT_REGISTER_URL, VALID_PATIENT_PAYLOAD, format="json")
        self.patient_token = pr.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")
        sr = self.client.post(PATIENT_SESSIONS_URL, {}, format="json")
        self.session_id = sr.data["id"]

    def _auth_doctor(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")

    def _auth_other_doctor(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.other_doctor_token}")

    def _auth_patient(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")

    def test_doctor_can_assign_self_to_session(self):
        self._auth_doctor()
        r = self.client.post(_assign_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("assigned_doctor", r.data)
        self.assertEqual(r.data["assigned_doctor"]["name"], VALID_DOCTOR_PAYLOAD["name"])

    def test_assignment_persists_in_session_detail(self):
        self._auth_doctor()
        self.client.post(_assign_url(self.session_id))
        r = self.client.get(f"{DOCTOR_SESSIONS_URL}{self.session_id}/")
        self.assertIsNotNone(r.data["assigned_doctor"])
        self.assertEqual(r.data["assigned_doctor"]["name"], VALID_DOCTOR_PAYLOAD["name"])

    def test_assignment_visible_in_session_list(self):
        self._auth_doctor()
        self.client.post(_assign_url(self.session_id))
        r = self.client.get(DOCTOR_SESSIONS_URL)
        self.assertIsNotNone(r.data[0]["assigned_doctor"])

    def test_assign_requires_auth(self):
        self.client.credentials()
        r = self.client.post(_assign_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_cannot_assign_session(self):
        self._auth_patient()
        r = self.client.post(_assign_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_second_doctor_cannot_overwrite_assignment(self):
        self._auth_doctor()
        self.client.post(_assign_url(self.session_id))
        self._auth_other_doctor()
        r = self.client.post(_assign_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)

    def test_doctor_can_reassign_own_session(self):
        self._auth_doctor()
        self.client.post(_assign_url(self.session_id))
        r = self.client.post(_assign_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_doctor_can_unassign_self(self):
        self._auth_doctor()
        self.client.post(_assign_url(self.session_id))
        r = self.client.delete(_assign_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)

    def test_unassign_clears_doctor_from_session(self):
        self._auth_doctor()
        self.client.post(_assign_url(self.session_id))
        self.client.delete(_assign_url(self.session_id))
        r = self.client.get(f"{DOCTOR_SESSIONS_URL}{self.session_id}/")
        self.assertIsNone(r.data["assigned_doctor"])

    def test_other_doctor_cannot_unassign(self):
        self._auth_doctor()
        self.client.post(_assign_url(self.session_id))
        self._auth_other_doctor()
        r = self.client.delete(_assign_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_assign_unknown_session_returns_404(self):
        self._auth_doctor()
        r = self.client.post(_assign_url("00000000-0000-0000-0000-000000000000"))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_patient_session_detail_shows_assigned_doctor(self):
        self._auth_doctor()
        self.client.post(_assign_url(self.session_id))
        self._auth_patient()
        r = self.client.get(f"{PATIENT_SESSIONS_URL}{self.session_id}/")
        self.assertIsNotNone(r.data["assigned_doctor"])
        self.assertEqual(r.data["assigned_doctor"]["name"], VALID_DOCTOR_PAYLOAD["name"])


DOCTOR_APPOINTMENTS_URL = "/api/doctor/appointments/"
PATIENT_APPOINTMENTS_URL = "/api/patient/appointments/"


def _doctor_apt_detail_url(apt_id):
    return f"{DOCTOR_APPOINTMENTS_URL}{apt_id}/"


class DoctorAppointmentTests(APITestCase):
    def setUp(self):
        dr = self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")
        self.doctor_token = dr.data["tokens"]["access"]
        self.doctor_id = dr.data["doctor_id"]

        pr = self.client.post(PATIENT_REGISTER_URL, VALID_PATIENT_PAYLOAD, format="json")
        self.patient_token = pr.data["tokens"]["access"]

        from django.utils import timezone
        from datetime import timedelta
        self.future_dt = (timezone.now() + timedelta(days=3)).isoformat()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")
        apt_r = self.client.post(
            PATIENT_APPOINTMENTS_URL,
            {"doctor": self.doctor_id, "scheduled_at": self.future_dt, "reason": "Checkup"},
            format="json",
        )
        self.apt_id = apt_r.data["id"]

    def _auth_doctor(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")

    def _auth_patient(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")

    def test_doctor_can_list_own_appointments(self):
        self._auth_doctor()
        r = self.client.get(DOCTOR_APPOINTMENTS_URL)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)

    def test_doctor_appointment_list_shows_patient_info(self):
        self._auth_doctor()
        r = self.client.get(DOCTOR_APPOINTMENTS_URL)
        apt = r.data[0]
        self.assertIn("patient_name", apt)
        self.assertIn("patient_age", apt)
        self.assertEqual(apt["patient_name"], VALID_PATIENT_PAYLOAD["name"])

    def test_doctor_can_get_appointment_detail(self):
        self._auth_doctor()
        r = self.client.get(_doctor_apt_detail_url(self.apt_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(str(r.data["id"]), self.apt_id)

    def test_doctor_can_confirm_appointment(self):
        self._auth_doctor()
        r = self.client.patch(_doctor_apt_detail_url(self.apt_id), {"status": "confirmed"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], "confirmed")

    def test_doctor_can_cancel_appointment(self):
        self._auth_doctor()
        r = self.client.patch(_doctor_apt_detail_url(self.apt_id), {"status": "cancelled"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], "cancelled")

    def test_doctor_can_add_notes_to_appointment(self):
        self._auth_doctor()
        r = self.client.patch(
            _doctor_apt_detail_url(self.apt_id),
            {"doctor_notes": "Patient is on aspirin."},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["doctor_notes"], "Patient is on aspirin.")

    def test_invalid_status_transition_rejected(self):
        self._auth_doctor()
        r = self.client.patch(_doctor_apt_detail_url(self.apt_id), {"status": "completed"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_transition_from_cancelled(self):
        self._auth_doctor()
        self.client.patch(_doctor_apt_detail_url(self.apt_id), {"status": "cancelled"}, format="json")
        r = self.client.patch(_doctor_apt_detail_url(self.apt_id), {"status": "confirmed"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_doctor_appointment_list_requires_auth(self):
        self.client.credentials()
        r = self.client.get(DOCTOR_APPOINTMENTS_URL)
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_cannot_access_doctor_appointment_endpoint(self):
        self._auth_patient()
        r = self.client.get(DOCTOR_APPOINTMENTS_URL)
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_filter_doctor_appointments_by_status(self):
        self._auth_doctor()
        self.client.patch(_doctor_apt_detail_url(self.apt_id), {"status": "confirmed"}, format="json")
        r = self.client.get(f"{DOCTOR_APPOINTMENTS_URL}?status=confirmed")
        self.assertEqual(len(r.data), 1)
        r2 = self.client.get(f"{DOCTOR_APPOINTMENTS_URL}?status=pending")
        self.assertEqual(len(r2.data), 0)

    def test_other_doctors_appointment_not_visible(self):
        second_doctor_payload = {
            **VALID_DOCTOR_PAYLOAD,
            "email": "other.doc@hospital.com",
            "license_number": "LIC-999",
        }
        dr2 = self.client.post(DOCTOR_REGISTER_URL, second_doctor_payload, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {dr2.data['tokens']['access']}")
        r = self.client.get(DOCTOR_APPOINTMENTS_URL)
        self.assertEqual(len(r.data), 0)


def _prescriptions_url(session_id):
    return f"/api/doctor/patients/sessions/{session_id}/prescriptions/"


def _prescription_detail_url(session_id, prescription_id):
    return f"/api/doctor/patients/sessions/{session_id}/prescriptions/{prescription_id}/"


VALID_PRESCRIPTION_PAYLOAD = {
    "medications": [
        {"name": "Amoxicillin", "dose": "500mg", "frequency": "3x daily", "duration": "7 days"}
    ],
    "instructions": "Take with food. Avoid alcohol.",
    "follow_up_date": "2026-07-01",
}


class DoctorPrescriptionTests(APITestCase):
    def setUp(self):
        dr = self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")
        self.doctor_token = dr.data["tokens"]["access"]

        second_doctor_payload = {
            **VALID_DOCTOR_PAYLOAD,
            "email": "other.doc@hospital.com",
            "license_number": "LIC-999",
        }
        dr2 = self.client.post(DOCTOR_REGISTER_URL, second_doctor_payload, format="json")
        self.other_doctor_token = dr2.data["tokens"]["access"]

        pr = self.client.post(PATIENT_REGISTER_URL, VALID_PATIENT_PAYLOAD, format="json")
        self.patient_token = pr.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")
        sr = self.client.post(PATIENT_SESSIONS_URL, {}, format="json")
        self.session_id = sr.data["id"]

    def _auth_doctor(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")

    def _auth_other_doctor(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.other_doctor_token}")

    def _auth_patient(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")

    def test_doctor_can_create_prescription(self):
        self._auth_doctor()
        r = self.client.post(_prescriptions_url(self.session_id), VALID_PRESCRIPTION_PAYLOAD, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", r.data)
        self.assertEqual(r.data["doctor_name"], VALID_DOCTOR_PAYLOAD["name"])

    def test_create_prescription_requires_auth(self):
        self.client.credentials()
        r = self.client.post(_prescriptions_url(self.session_id), VALID_PRESCRIPTION_PAYLOAD, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_cannot_create_prescription(self):
        self._auth_patient()
        r = self.client.post(_prescriptions_url(self.session_id), VALID_PRESCRIPTION_PAYLOAD, format="json")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_empty_medications_list_rejected(self):
        self._auth_doctor()
        payload = {**VALID_PRESCRIPTION_PAYLOAD, "medications": []}
        r = self.client.post(_prescriptions_url(self.session_id), payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_medications_rejected(self):
        self._auth_doctor()
        payload = {"instructions": "Rest well.", "follow_up_date": "2026-07-01"}
        r = self.client.post(_prescriptions_url(self.session_id), payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_doctor_can_list_prescriptions_for_session(self):
        self._auth_doctor()
        self.client.post(_prescriptions_url(self.session_id), VALID_PRESCRIPTION_PAYLOAD, format="json")
        r = self.client.get(_prescriptions_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)

    def test_unknown_session_returns_404(self):
        self._auth_doctor()
        r = self.client.post(
            _prescriptions_url("00000000-0000-0000-0000-000000000000"),
            VALID_PRESCRIPTION_PAYLOAD,
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_doctor_can_get_prescription_detail(self):
        self._auth_doctor()
        create_r = self.client.post(_prescriptions_url(self.session_id), VALID_PRESCRIPTION_PAYLOAD, format="json")
        rx_id = create_r.data["id"]
        r = self.client.get(_prescription_detail_url(self.session_id, rx_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["instructions"], VALID_PRESCRIPTION_PAYLOAD["instructions"])

    def test_doctor_can_update_own_prescription(self):
        self._auth_doctor()
        create_r = self.client.post(_prescriptions_url(self.session_id), VALID_PRESCRIPTION_PAYLOAD, format="json")
        rx_id = create_r.data["id"]
        r = self.client.patch(
            _prescription_detail_url(self.session_id, rx_id),
            {"instructions": "Updated instructions."},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["instructions"], "Updated instructions.")

    def test_other_doctor_cannot_update_prescription(self):
        self._auth_doctor()
        create_r = self.client.post(_prescriptions_url(self.session_id), VALID_PRESCRIPTION_PAYLOAD, format="json")
        rx_id = create_r.data["id"]
        self._auth_other_doctor()
        r = self.client.patch(
            _prescription_detail_url(self.session_id, rx_id),
            {"instructions": "Hijacked."},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_doctor_can_read_prescription(self):
        self._auth_doctor()
        create_r = self.client.post(_prescriptions_url(self.session_id), VALID_PRESCRIPTION_PAYLOAD, format="json")
        rx_id = create_r.data["id"]
        self._auth_other_doctor()
        r = self.client.get(_prescription_detail_url(self.session_id, rx_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_doctor_can_delete_own_prescription(self):
        self._auth_doctor()
        create_r = self.client.post(_prescriptions_url(self.session_id), VALID_PRESCRIPTION_PAYLOAD, format="json")
        rx_id = create_r.data["id"]
        r = self.client.delete(_prescription_detail_url(self.session_id, rx_id))
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)

    def test_other_doctor_cannot_delete_prescription(self):
        self._auth_doctor()
        create_r = self.client.post(_prescriptions_url(self.session_id), VALID_PRESCRIPTION_PAYLOAD, format="json")
        rx_id = create_r.data["id"]
        self._auth_other_doctor()
        r = self.client.delete(_prescription_detail_url(self.session_id, rx_id))
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_prescription_fields_present(self):
        self._auth_doctor()
        create_r = self.client.post(_prescriptions_url(self.session_id), VALID_PRESCRIPTION_PAYLOAD, format="json")
        for field in ["id", "doctor_name", "session_id", "medications", "instructions", "follow_up_date", "created_at"]:
            self.assertIn(field, create_r.data)


# ── New AI Feature Tests ───────────────────────────────────────────────────────

def _ai_diagnosis_url(session_id):
    return f"/api/doctor/patients/sessions/{session_id}/ai-diagnosis/"


def _note_draft_url(session_id):
    return f"/api/doctor/patients/sessions/{session_id}/notes/draft/"


def _drug_check_url(session_id):
    return f"/api/doctor/patients/sessions/{session_id}/prescriptions/check-interactions/"


def _cross_summary_url(patient_id):
    return f"/api/doctor/patients/{patient_id}/summary/"


_MOCK_DIAGNOSIS = {
    "differentials": [
        {"condition": "Migraine", "likelihood": "high", "reasoning": "Throbbing pain with nausea."}
    ],
    "recommended_workup": ["Neurological exam"],
    "caution": "AI-generated suggestions only.",
}

_MOCK_DRUG_RESULT_SAFE = {
    "interactions_found": [],
    "safe_to_prescribe": True,
    "caution": "AI check only.",
}

_MOCK_DRUG_RESULT_INTERACTION = {
    "interactions_found": [
        {"drugs": ["Warfarin", "Aspirin"], "severity": "high", "explanation": "Increased bleeding risk."}
    ],
    "safe_to_prescribe": False,
    "caution": "AI check only.",
}

_MOCK_CROSS_SUMMARY = {
    "patient_name": "Ali Khan",
    "session_count": 1,
    "date_range": {"from": "2026-01-01T00:00:00+00:00", "to": "2026-01-01T00:00:00+00:00"},
    "sessions": [],
    "trend_analysis": "Recurring headaches noted.",
}

_MOCK_SUMMARY = {
    "chief_complaint": "Headache for two days.",
    "symptom_details": {},
    "risk_level": "routine",
    "recommended_action": "See GP within a week.",
    "notes_for_doctor": "",
    "generated_at": "2026-06-21T10:00:00+00:00",
}


class _DoctorAIBase(APITestCase):
    """Shared setUp for doctor AI feature tests."""

    def setUp(self):
        dr = self.client.post(DOCTOR_REGISTER_URL, VALID_DOCTOR_PAYLOAD, format="json")
        self.doctor_token = dr.data["tokens"]["access"]

        pr = self.client.post(PATIENT_REGISTER_URL, VALID_PATIENT_PAYLOAD, format="json")
        self.patient_token = pr.data["tokens"]["access"]
        self.patient_id = pr.data["patient_id"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")
        sr = self.client.post(PATIENT_SESSIONS_URL, {}, format="json")
        self.session_id = sr.data["id"]

    def _auth_doctor(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_token}")

    def _auth_patient(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.patient_token}")

    def _send_patient_message(self):
        with patch("patient.views.detect_emergency", return_value=_NON_EMERGENCY), \
             patch("patient.views.detect_intent", return_value=_SYMPTOM_INTENT), \
             patch("patient.views.run_triage_graph", return_value=_MOCK_GRAPH_RESULT):
            self.client.post(
                f"{PATIENT_SESSIONS_URL}{self.session_id}/messages/",
                {"content": "I have a headache."},
                format="json",
            )

    def _put_session_summary(self):
        from patient.models import ChatSession
        ChatSession.objects.filter(id=self.session_id).update(summary=_MOCK_SUMMARY)


class AIDiagnosisTests(_DoctorAIBase):
    """POST /api/doctor/patients/sessions/<id>/ai-diagnosis/"""

    def test_happy_path_returns_201(self):
        self._send_patient_message()
        self._auth_doctor()
        with patch("doctor.ai_features.generate_differential_diagnosis", return_value=_MOCK_DIAGNOSIS):
            r = self.client.post(_ai_diagnosis_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIn("content", r.data)
        self.assertIn("differentials", r.data["content"])

    def test_no_messages_returns_400(self):
        self._auth_doctor()
        with patch(
            "doctor.ai_features.generate_differential_diagnosis",
            side_effect=ValueError("Session has no messages to analyse."),
        ):
            r = self.client.post(_ai_diagnosis_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", r.data)

    def test_requires_auth(self):
        self.client.credentials()
        r = self.client.post(_ai_diagnosis_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_token_returns_404(self):
        self._auth_patient()
        with patch("doctor.ai_features.generate_differential_diagnosis", return_value=_MOCK_DIAGNOSIS):
            r = self.client.post(_ai_diagnosis_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_session_returns_404(self):
        self._auth_doctor()
        with patch("doctor.ai_features.generate_differential_diagnosis", return_value=_MOCK_DIAGNOSIS):
            r = self.client.post(_ai_diagnosis_url("00000000-0000-0000-0000-000000000000"))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_llm_failure_returns_503(self):
        self._send_patient_message()
        self._auth_doctor()
        with patch("doctor.ai_features.generate_differential_diagnosis", side_effect=Exception("LLM down")):
            r = self.client.post(_ai_diagnosis_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


class DoctorNoteDraftTests(_DoctorAIBase):
    """POST /api/doctor/patients/sessions/<id>/notes/draft/"""

    def test_happy_path_returns_draft(self):
        self._put_session_summary()
        self._auth_doctor()
        with patch("doctor.ai_features.generate_soap_draft", return_value="DRAFT: SUBJECTIVE: Headache..."):
            r = self.client.post(_note_draft_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("draft", r.data)
        self.assertIsInstance(r.data["draft"], str)

    def test_no_summary_returns_400(self):
        self._auth_doctor()
        with patch(
            "doctor.ai_features.generate_soap_draft",
            side_effect=ValueError("Session has no clinical summary."),
        ):
            r = self.client.post(_note_draft_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", r.data)

    def test_requires_auth(self):
        self.client.credentials()
        r = self.client.post(_note_draft_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_token_returns_404(self):
        self._put_session_summary()
        self._auth_patient()
        with patch("doctor.ai_features.generate_soap_draft", return_value="DRAFT"):
            r = self.client.post(_note_draft_url(self.session_id))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_session_returns_404(self):
        self._auth_doctor()
        with patch("doctor.ai_features.generate_soap_draft", return_value="DRAFT"):
            r = self.client.post(_note_draft_url("00000000-0000-0000-0000-000000000000"))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


class DrugInteractionCheckTests(_DoctorAIBase):
    """POST /api/doctor/patients/sessions/<id>/prescriptions/check-interactions/"""

    def test_safe_medications_returns_200(self):
        self._auth_doctor()
        with patch("doctor.ai_features.check_drug_interactions", return_value=_MOCK_DRUG_RESULT_SAFE):
            r = self.client.post(
                _drug_check_url(self.session_id),
                {"medications": ["Paracetamol"]},
                format="json",
            )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["safe_to_prescribe"])
        self.assertEqual(r.data["interactions_found"], [])

    def test_interaction_found_returns_details(self):
        self._auth_doctor()
        with patch("doctor.ai_features.check_drug_interactions", return_value=_MOCK_DRUG_RESULT_INTERACTION):
            r = self.client.post(
                _drug_check_url(self.session_id),
                {"medications": ["Warfarin", "Aspirin"]},
                format="json",
            )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data["safe_to_prescribe"])
        self.assertEqual(len(r.data["interactions_found"]), 1)

    def test_empty_medications_returns_400(self):
        self._auth_doctor()
        r = self.client.post(
            _drug_check_url(self.session_id),
            {"medications": []},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_medications_key_returns_400(self):
        self._auth_doctor()
        r = self.client.post(_drug_check_url(self.session_id), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_auth(self):
        self.client.credentials()
        r = self.client.post(_drug_check_url(self.session_id), {"medications": ["X"]}, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_token_returns_404(self):
        self._auth_patient()
        with patch("doctor.ai_features.check_drug_interactions", return_value=_MOCK_DRUG_RESULT_SAFE):
            r = self.client.post(
                _drug_check_url(self.session_id),
                {"medications": ["Paracetamol"]},
                format="json",
            )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_session_returns_404(self):
        self._auth_doctor()
        with patch("doctor.ai_features.check_drug_interactions", return_value=_MOCK_DRUG_RESULT_SAFE):
            r = self.client.post(
                _drug_check_url("00000000-0000-0000-0000-000000000000"),
                {"medications": ["Paracetamol"]},
                format="json",
            )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


class PatientCrossSummaryTests(_DoctorAIBase):
    """GET /api/doctor/patients/<id>/summary/"""

    def test_patient_with_no_sessions_returns_empty(self):
        self._auth_doctor()
        r = self.client.get(_cross_summary_url(self.patient_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["session_count"], 0)
        self.assertEqual(r.data["sessions"], [])
        self.assertIsNone(r.data["trend_analysis"])

    def test_sessions_without_summary_excluded(self):
        self._auth_doctor()
        r = self.client.get(_cross_summary_url(self.patient_id))
        self.assertEqual(r.data["session_count"], 0)

    def test_sessions_with_summary_included(self):
        self._put_session_summary()
        self._auth_doctor()
        with patch("doctor.ai_features.generate_cross_session_summary", return_value=_MOCK_CROSS_SUMMARY):
            r = self.client.get(_cross_summary_url(self.patient_id))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("sessions", r.data)
        self.assertIn("patient_name", r.data)

    def test_unknown_patient_returns_404(self):
        self._auth_doctor()
        r = self.client.get(_cross_summary_url("00000000-0000-0000-0000-000000000000"))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_requires_auth(self):
        self.client.credentials()
        r = self.client.get(_cross_summary_url(self.patient_id))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_token_returns_404(self):
        self._auth_patient()
        r = self.client.get(_cross_summary_url(self.patient_id))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_analyze_false_skips_llm(self):
        self._put_session_summary()
        self._auth_doctor()
        with patch("doctor.ai_features.generate_cross_session_summary") as mock_llm:
            r = self.client.get(f"{_cross_summary_url(self.patient_id)}?analyze=false")
        mock_llm.assert_not_called()
        self.assertEqual(r.status_code, status.HTTP_200_OK)


class AIPrioritizedQueueTests(_DoctorAIBase):
    """GET /api/doctor/patients/sessions/?ai_prioritized=true"""

    def _set_risk(self, risk_level):
        from patient.models import ChatSession
        ChatSession.objects.filter(id=self.session_id).update(risk_level=risk_level)

    def _create_extra_session(self, risk_level, assign=False):
        other_patient_payload = {
            **VALID_PATIENT_PAYLOAD,
            "email": f"extra_{risk_level}@example.com",
            "phone": f"0300000{hash(risk_level) % 10000:04d}",
        }
        pr = self.client.post(PATIENT_REGISTER_URL, other_patient_payload, format="json")
        token = pr.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        sr = self.client.post(PATIENT_SESSIONS_URL, {}, format="json")
        sid = sr.data["id"]
        from patient.models import ChatSession
        ChatSession.objects.filter(id=sid).update(risk_level=risk_level)
        return sid

    def test_emergency_session_appears_first(self):
        self._set_risk("routine")
        emergency_sid = self._create_extra_session("emergency")

        self._auth_doctor()
        r = self.client.get(f"{DOCTOR_SESSIONS_URL}?ai_prioritized=true")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(str(r.data[0]["session_id"]), emergency_sid)

    def test_urgent_before_routine(self):
        self._set_risk("routine")
        urgent_sid = self._create_extra_session("urgent")

        self._auth_doctor()
        r = self.client.get(f"{DOCTOR_SESSIONS_URL}?ai_prioritized=true")
        ids = [str(s["session_id"]) for s in r.data]
        self.assertLess(ids.index(urgent_sid), ids.index(self.session_id))

    def test_without_param_returns_default_order(self):
        self._auth_doctor()
        r = self.client.get(DOCTOR_SESSIONS_URL)
        self.assertEqual(r.status_code, status.HTTP_200_OK)


class AuditLogTests(_DoctorAIBase):
    """AuditLog is created on key doctor actions."""

    def test_view_session_creates_audit_log(self):
        from doctor.models import AuditLog
        self._auth_doctor()
        self.client.get(f"{DOCTOR_SESSIONS_URL}{self.session_id}/")
        self.assertTrue(AuditLog.objects.filter(action="view_session").exists())

    def test_create_note_creates_audit_log(self):
        from doctor.models import AuditLog
        self._auth_doctor()
        self.client.post(_notes_url(self.session_id), {"note": "Audit test note."}, format="json")
        self.assertTrue(AuditLog.objects.filter(action="create_note").exists())

    def test_assign_session_creates_audit_log(self):
        from doctor.models import AuditLog
        self._auth_doctor()
        self.client.post(f"{DOCTOR_SESSIONS_URL}{self.session_id}/assign/")
        self.assertTrue(AuditLog.objects.filter(action="assign_session").exists())

    def test_create_prescription_creates_audit_log(self):
        from doctor.models import AuditLog
        self._auth_doctor()
        self.client.post(_prescriptions_url(self.session_id), VALID_PRESCRIPTION_PAYLOAD, format="json")
        self.assertTrue(AuditLog.objects.filter(action="create_prescription").exists())

    def test_ai_diagnosis_creates_audit_log(self):
        from doctor.models import AuditLog
        self._send_patient_message()
        self._auth_doctor()
        with patch("doctor.ai_features.generate_differential_diagnosis", return_value=_MOCK_DIAGNOSIS):
            self.client.post(_ai_diagnosis_url(self.session_id))
        self.assertTrue(AuditLog.objects.filter(action="generate_diagnosis").exists())

    def test_patient_action_does_not_create_log(self):
        from doctor.models import AuditLog
        self._auth_patient()
        self.client.get(f"{DOCTOR_SESSIONS_URL}{self.session_id}/")
        self.assertEqual(AuditLog.objects.count(), 0)
