import json
import uuid
from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Agent, AgentFact, AgentMessage, AgentSession, ConversationSummary
from .services import MESSAGES_TO_KEEP, SUMMARIZE_THRESHOLD

# ── URL constants ──────────────────────────────────────────────────────────────
REGISTER_URL = "/api/patient/register/"
LOGIN_URL = "/api/patient/login/"
AGENTS_URL = "/api/agents/agents/"


def session_url(agent_id):
    return f"/api/agents/agents/{agent_id}/sessions/"


def agent_detail_url(agent_id):
    return f"/api/agents/agents/{agent_id}/"


def session_detail_url(session_id):
    return f"/api/agents/sessions/{session_id}/"


def session_messages_url(session_id):
    return f"/api/agents/sessions/{session_id}/messages/"


def agent_facts_url(agent_id):
    return f"/api/agents/agents/{agent_id}/facts/"


def fact_delete_url(agent_id, fact_id):
    return f"/api/agents/agents/{agent_id}/facts/{fact_id}/"


# ── Fixture data ───────────────────────────────────────────────────────────────
VALID_USER = {
    "name": "Jane Doe",
    "age": 28,
    "gender": "female",
    "phone": "03001234567",
    "email": "jane@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!",
}

VALID_USER_2 = {
    "name": "Bob Smith",
    "age": 35,
    "gender": "male",
    "phone": "03009876543",
    "email": "bob@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!",
}

VALID_AGENT = {
    "name": "My Assistant",
    "instructions": "You are a helpful and concise assistant.",
}

MOCK_LLM_REPLY = "This is the assistant's response."
MOCK_SUMMARY_JSON = json.dumps(
    {"summary": "User asked about Python.", "facts": ["User prefers Python over Java."]}
)


# ── Shared base ────────────────────────────────────────────────────────────────
class AuthenticatedTestCase(APITestCase):
    def setUp(self):
        self.client.post(REGISTER_URL, VALID_USER, format="json")
        resp = self.client.post(
            LOGIN_URL,
            {"email": VALID_USER["email"], "password": VALID_USER["password"]},
            format="json",
        )
        self.token = resp.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def _create_agent(self, payload=None):
        return self.client.post(AGENTS_URL, payload or VALID_AGENT, format="json")

    def _create_session(self, agent_id, title="Test session"):
        return self.client.post(session_url(agent_id), {"title": title}, format="json")


# ── Agent CRUD ─────────────────────────────────────────────────────────────────
class AgentCRUDTests(AuthenticatedTestCase):

    def test_create_agent_success(self):
        resp = self._create_agent()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", resp.data)
        self.assertEqual(resp.data["name"], VALID_AGENT["name"])
        self.assertEqual(resp.data["instructions"], VALID_AGENT["instructions"])

    def test_list_agents_returns_only_own(self):
        self._create_agent()
        # second user creates their own agent
        self.client.post(REGISTER_URL, VALID_USER_2, format="json")
        r2 = self.client.post(
            LOGIN_URL,
            {"email": VALID_USER_2["email"], "password": VALID_USER_2["password"]},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r2.data['tokens']['access']}")
        self.client.post(AGENTS_URL, {"name": "Other", "instructions": "..."}, format="json")

        # restore first user
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        resp = self.client.get(AGENTS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_get_agent_detail(self):
        agent_id = self._create_agent().data["id"]
        resp = self.client.get(agent_detail_url(agent_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], VALID_AGENT["name"])

    def test_update_agent_put(self):
        agent_id = self._create_agent().data["id"]
        resp = self.client.put(
            agent_detail_url(agent_id),
            {"name": "Updated", "instructions": "New instructions."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Updated")

    def test_update_agent_patch(self):
        agent_id = self._create_agent().data["id"]
        resp = self.client.patch(
            agent_detail_url(agent_id), {"name": "Patched"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Patched")

    def test_delete_agent(self):
        agent_id = self._create_agent().data["id"]
        resp = self.client.delete(agent_detail_url(agent_id))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Agent.objects.filter(id=agent_id).exists())

    def test_create_agent_missing_name(self):
        resp = self._create_agent({"instructions": "..."})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_agent_missing_instructions(self):
        resp = self._create_agent({"name": "X"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_auth_required_list(self):
        self.client.credentials()
        resp = self.client.get(AGENTS_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_auth_required_create(self):
        self.client.credentials()
        resp = self._create_agent()
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_user_cannot_access_agent(self):
        agent_id = self._create_agent().data["id"]
        self.client.post(REGISTER_URL, VALID_USER_2, format="json")
        r2 = self.client.post(
            LOGIN_URL,
            {"email": VALID_USER_2["email"], "password": VALID_USER_2["password"]},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r2.data['tokens']['access']}")
        resp = self.client.get(agent_detail_url(agent_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_user_cannot_delete_agent(self):
        agent_id = self._create_agent().data["id"]
        self.client.post(REGISTER_URL, VALID_USER_2, format="json")
        r2 = self.client.post(
            LOGIN_URL,
            {"email": VALID_USER_2["email"], "password": VALID_USER_2["password"]},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r2.data['tokens']['access']}")
        resp = self.client.delete(agent_detail_url(agent_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Agent.objects.filter(id=agent_id).exists())


# ── Session CRUD ───────────────────────────────────────────────────────────────
class AgentSessionTests(AuthenticatedTestCase):

    def test_create_session_success(self):
        agent_id = self._create_agent().data["id"]
        resp = self._create_session(agent_id)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", resp.data)
        self.assertTrue(resp.data["is_active"])

    def test_create_session_with_title(self):
        agent_id = self._create_agent().data["id"]
        resp = self._create_session(agent_id, title="Planning chat")
        self.assertEqual(resp.data["title"], "Planning chat")

    def test_create_session_without_title(self):
        agent_id = self._create_agent().data["id"]
        resp = self.client.post(session_url(agent_id), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["title"], "")

    def test_list_sessions_for_agent(self):
        agent_id = self._create_agent().data["id"]
        self._create_session(agent_id, "S1")
        self._create_session(agent_id, "S2")
        resp = self.client.get(session_url(agent_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)

    def test_session_detail_includes_context(self):
        agent_id = self._create_agent().data["id"]
        session_id = self._create_session(agent_id).data["id"]
        resp = self.client.get(session_detail_url(session_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("recent_messages", resp.data)
        self.assertIn("summary", resp.data)
        self.assertIn("facts", resp.data)
        self.assertEqual(resp.data["summary"], None)

    def test_close_session_via_patch(self):
        agent_id = self._create_agent().data["id"]
        session_id = self._create_session(agent_id).data["id"]
        resp = self.client.patch(
            session_detail_url(session_id), {"is_active": False}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["is_active"])

    def test_delete_session(self):
        agent_id = self._create_agent().data["id"]
        session_id = self._create_session(agent_id).data["id"]
        resp = self.client.delete(session_detail_url(session_id))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AgentSession.objects.filter(id=session_id).exists())

    def test_auth_required_create_session(self):
        agent_id = self._create_agent().data["id"]
        self.client.credentials()
        resp = self._create_session(agent_id)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_session_on_nonexistent_agent_returns_404(self):
        resp = self._create_session(uuid.uuid4())
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_user_cannot_access_session(self):
        agent_id = self._create_agent().data["id"]
        session_id = self._create_session(agent_id).data["id"]
        self.client.post(REGISTER_URL, VALID_USER_2, format="json")
        r2 = self.client.post(
            LOGIN_URL,
            {"email": VALID_USER_2["email"], "password": VALID_USER_2["password"]},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r2.data['tokens']['access']}")
        resp = self.client.get(session_detail_url(session_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ── Messaging ──────────────────────────────────────────────────────────────────
class AgentMessageTests(AuthenticatedTestCase):

    def setUp(self):
        super().setUp()
        agent_id = self._create_agent().data["id"]
        self.session_id = self._create_session(agent_id).data["id"]

    @patch("agents.services._call_llm", return_value=MOCK_LLM_REPLY)
    def test_send_message_success(self, _mock):
        resp = self.client.post(
            session_messages_url(self.session_id),
            {"content": "Hello!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["reply"], MOCK_LLM_REPLY)

    @patch("agents.services._call_llm", return_value=MOCK_LLM_REPLY)
    def test_messages_are_persisted(self, _mock):
        self.client.post(
            session_messages_url(self.session_id),
            {"content": "Hello!"},
            format="json",
        )
        session = AgentSession.objects.get(id=self.session_id)
        self.assertEqual(session.messages.count(), 2)  # user + assistant

    @patch("agents.services._call_llm", return_value=MOCK_LLM_REPLY)
    def test_get_messages_returns_recent(self, _mock):
        self.client.post(
            session_messages_url(self.session_id), {"content": "Hi"}, format="json"
        )
        resp = self.client.get(session_messages_url(self.session_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(resp.data[0]["role"], "user")
        self.assertEqual(resp.data[1]["role"], "assistant")

    def test_send_empty_content_rejected(self):
        resp = self.client.post(
            session_messages_url(self.session_id), {"content": ""}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_message_to_closed_session_rejected(self):
        self.client.patch(
            session_detail_url(self.session_id), {"is_active": False}, format="json"
        )
        resp = self.client.post(
            session_messages_url(self.session_id),
            {"content": "Still here?"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("closed", resp.data["detail"])

    def test_auth_required_send_message(self):
        self.client.credentials()
        resp = self.client.post(
            session_messages_url(self.session_id),
            {"content": "Hi"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_user_cannot_send_message(self):
        self.client.post(REGISTER_URL, VALID_USER_2, format="json")
        r2 = self.client.post(
            LOGIN_URL,
            {"email": VALID_USER_2["email"], "password": VALID_USER_2["password"]},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r2.data['tokens']['access']}")
        resp = self.client.post(
            session_messages_url(self.session_id),
            {"content": "Sneaky"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("agents.services._call_llm", return_value=MOCK_LLM_REPLY)
    def test_instructions_used_as_system_prompt(self, mock_llm):
        self.client.post(
            session_messages_url(self.session_id), {"content": "Hi"}, format="json"
        )
        call_args = mock_llm.call_args
        system_prompt = call_args[0][0]
        self.assertIn(VALID_AGENT["instructions"], system_prompt)


# ── Summarization ──────────────────────────────────────────────────────────────
class SummarizationTests(AuthenticatedTestCase):
    """Tests for the automatic summarization and fact-extraction pipeline."""

    def setUp(self):
        super().setUp()
        agent_resp = self._create_agent()
        self.agent_id = agent_resp.data["id"]
        self.agent = Agent.objects.get(id=self.agent_id)
        session_resp = self._create_session(self.agent_id)
        self.session = AgentSession.objects.get(id=session_resp.data["id"])

    def _bulk_create_messages(self, count):
        """Directly insert messages into the DB to bypass the LLM call."""
        msgs = []
        for i in range(count):
            role = "user" if i % 2 == 0 else "assistant"
            msgs.append(
                AgentMessage(session=self.session, role=role, content=f"Message {i}")
            )
        AgentMessage.objects.bulk_create(msgs)

    @patch("agents.services._call_llm", return_value=MOCK_SUMMARY_JSON)
    def test_summarization_triggers_above_threshold(self, _mock):
        self._bulk_create_messages(SUMMARIZE_THRESHOLD + 1)
        from agents.services import summarize_if_needed
        summarize_if_needed(self.session)

        self.assertEqual(self.session.summaries.count(), 1)
        summary = self.session.summaries.first()
        self.assertIn("Python", summary.content)

    @patch("agents.services._call_llm", return_value=MOCK_SUMMARY_JSON)
    def test_summarization_extracts_facts(self, _mock):
        self._bulk_create_messages(SUMMARIZE_THRESHOLD + 1)
        from agents.services import summarize_if_needed
        summarize_if_needed(self.session)

        facts = list(self.agent.facts.values_list("fact", flat=True))
        self.assertIn("User prefers Python over Java.", facts)

    @patch("agents.services._call_llm", return_value=MOCK_SUMMARY_JSON)
    def test_summarized_messages_marked(self, _mock):
        self._bulk_create_messages(SUMMARIZE_THRESHOLD + 1)
        from agents.services import summarize_if_needed
        summarize_if_needed(self.session)

        summarized = self.session.messages.filter(is_summarized=True).count()
        unsummarized = self.session.messages.filter(is_summarized=False).count()
        self.assertEqual(unsummarized, MESSAGES_TO_KEEP)
        self.assertGreater(summarized, 0)

    def test_summarization_does_not_trigger_below_threshold(self):
        self._bulk_create_messages(SUMMARIZE_THRESHOLD - 1)
        from agents.services import summarize_if_needed
        summarize_if_needed(self.session)
        self.assertEqual(self.session.summaries.count(), 0)

    @patch("agents.services._call_llm", return_value=MOCK_SUMMARY_JSON)
    def test_summary_included_in_subsequent_system_prompt(self, mock_llm):
        self._bulk_create_messages(SUMMARIZE_THRESHOLD + 1)
        from agents.services import summarize_if_needed, _build_system_prompt
        summarize_if_needed(self.session)

        prompt = _build_system_prompt(self.agent, self.session)
        self.assertIn("Previous Conversation Summary", prompt)
        self.assertIn("Python", prompt)

    @patch("agents.services._call_llm", return_value=MOCK_SUMMARY_JSON)
    def test_facts_included_in_system_prompt(self, mock_llm):
        self._bulk_create_messages(SUMMARIZE_THRESHOLD + 1)
        from agents.services import summarize_if_needed, _build_system_prompt
        summarize_if_needed(self.session)

        prompt = _build_system_prompt(self.agent, self.session)
        self.assertIn("Known Facts About the User", prompt)
        self.assertIn("Python", prompt)

    @patch("agents.services._call_llm", return_value="not valid json at all")
    def test_summarization_handles_malformed_llm_response(self, _mock):
        self._bulk_create_messages(SUMMARIZE_THRESHOLD + 1)
        from agents.services import summarize_if_needed
        summarize_if_needed(self.session)
        # Should still create a summary with the raw text, no crash
        self.assertEqual(self.session.summaries.count(), 1)


# ── Facts management ───────────────────────────────────────────────────────────
class AgentFactTests(AuthenticatedTestCase):

    def setUp(self):
        super().setUp()
        self.agent_id = self._create_agent().data["id"]
        self.agent = Agent.objects.get(id=self.agent_id)

    def _create_fact(self):
        return AgentFact.objects.create(agent=self.agent, fact="User likes dogs.")

    def test_list_facts(self):
        self._create_fact()
        resp = self.client.get(agent_facts_url(self.agent_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["fact"], "User likes dogs.")

    def test_list_facts_empty(self):
        resp = self.client.get(agent_facts_url(self.agent_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

    def test_delete_fact(self):
        fact = self._create_fact()
        resp = self.client.delete(fact_delete_url(self.agent_id, fact.id))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(AgentFact.objects.filter(id=fact.id).exists())

    def test_delete_nonexistent_fact_returns_404(self):
        resp = self.client.delete(fact_delete_url(self.agent_id, uuid.uuid4()))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_auth_required_list_facts(self):
        self.client.credentials()
        resp = self.client.get(agent_facts_url(self.agent_id))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_user_cannot_list_facts(self):
        self.client.post(REGISTER_URL, VALID_USER_2, format="json")
        r2 = self.client.post(
            LOGIN_URL,
            {"email": VALID_USER_2["email"], "password": VALID_USER_2["password"]},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r2.data['tokens']['access']}")
        resp = self.client.get(agent_facts_url(self.agent_id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
