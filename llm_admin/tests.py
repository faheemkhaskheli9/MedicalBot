from unittest.mock import patch, MagicMock
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User
from .models import LLMModel, Tool, LLMModelTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_MODEL_PAYLOAD = {
    "name": "Test GPT",
    "provider": "openai",
    "model_id": "gpt-4o-mini",
    "temperature": 0.7,
}

VALID_TOOL_PAYLOAD = {
    "name": "test-tool",
    "display_name": "Test Tool",
    "description": "A tool for testing.",
    "tool_type": "built_in",
    "implementation": "llm_admin.builtin_tools.web_search.run",
    "parameters_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
}


def make_admin_user(email="admin@test.com", password="Admin1234!"):
    return User.objects.create_user(email=email, password=password, role="hospital_admin")


def make_patient_user(email="patient@test.com", password="Patient1234!"):
    return User.objects.create_user(email=email, password=password, role="patient")


def get_access_token(user):
    """Generate a JWT access token directly, bypassing the login endpoint."""
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


# ---------------------------------------------------------------------------
# Permission tests
# ---------------------------------------------------------------------------

class PermissionTests(APITestCase):
    def setUp(self):
        self.patient = make_patient_user()
        self.admin = make_admin_user()

    def test_unauthenticated_cannot_list_models(self):
        resp = self.client.get("/api/llm-admin/models/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_cannot_list_models(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_access_token(self.patient)}")
        resp = self.client.get("/api/llm-admin/models/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_models(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_access_token(self.admin)}")
        resp = self.client.get("/api/llm-admin/models/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unauthenticated_cannot_list_tools(self):
        resp = self.client.get("/api/llm-admin/tools/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patient_cannot_list_tools(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_access_token(self.patient)}")
        resp = self.client.get("/api/llm-admin/tools/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# LLMModel CRUD tests
# ---------------------------------------------------------------------------

class LLMModelCRUDTests(APITestCase):
    def setUp(self):
        self.admin = make_admin_user(email="modeladmin@test.com")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_access_token(self.admin)}")

    def test_create_llm_model(self):
        resp = self.client.post("/api/llm-admin/models/", VALID_MODEL_PAYLOAD, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["name"], "Test GPT")
        self.assertNotIn("api_key", resp.data)  # write_only

    def test_api_key_never_returned(self):
        payload = {**VALID_MODEL_PAYLOAD, "name": "Key Test", "api_key": "sk-secret123"}
        resp = self.client.post("/api/llm-admin/models/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("api_key", resp.data)

    def test_list_llm_models(self):
        LLMModel.objects.create(**VALID_MODEL_PAYLOAD)
        resp = self.client.get("/api/llm-admin/models/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_retrieve_llm_model(self):
        obj = LLMModel.objects.create(**VALID_MODEL_PAYLOAD)
        resp = self.client.get(f"/api/llm-admin/models/{obj.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], obj.name)

    def test_update_llm_model(self):
        obj = LLMModel.objects.create(**VALID_MODEL_PAYLOAD)
        resp = self.client.patch(f"/api/llm-admin/models/{obj.id}/", {"temperature": 0.2}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(float(resp.data["temperature"]), 0.2)

    def test_delete_llm_model(self):
        obj = LLMModel.objects.create(**VALID_MODEL_PAYLOAD)
        resp = self.client.delete(f"/api/llm-admin/models/{obj.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LLMModel.objects.filter(pk=obj.id).exists())

    def test_404_on_missing_model(self):
        resp = self.client.get("/api/llm-admin/models/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_is_default_enforced(self):
        obj1 = LLMModel.objects.create(**{**VALID_MODEL_PAYLOAD, "name": "Model1", "is_default": True})
        obj2 = LLMModel.objects.create(**{**VALID_MODEL_PAYLOAD, "name": "Model2", "is_default": True})
        obj1.refresh_from_db()
        self.assertFalse(obj1.is_default)
        self.assertTrue(obj2.is_default)

    def test_set_default_endpoint(self):
        obj = LLMModel.objects.create(**VALID_MODEL_PAYLOAD)
        resp = self.client.post(f"/api/llm-admin/models/{obj.id}/set-default/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        obj.refresh_from_db()
        self.assertTrue(obj.is_default)

    def test_invalid_temperature(self):
        payload = {**VALID_MODEL_PAYLOAD, "name": "BadTemp", "temperature": 5.0}
        resp = self.client.post("/api/llm-admin/models/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ollama_requires_base_url(self):
        payload = {**VALID_MODEL_PAYLOAD, "name": "OllamaTest", "provider": "ollama"}
        resp = self.client.post("/api/llm-admin/models/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("base_url", str(resp.data))


# ---------------------------------------------------------------------------
# Tool CRUD tests
# ---------------------------------------------------------------------------

class ToolCRUDTests(APITestCase):
    def setUp(self):
        self.admin = make_admin_user(email="tooladmin@test.com")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_access_token(self.admin)}")

    def test_create_tool(self):
        resp = self.client.post("/api/llm-admin/tools/", VALID_TOOL_PAYLOAD, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["name"], VALID_TOOL_PAYLOAD["name"])

    def test_list_tools(self):
        resp = self.client.get("/api/llm-admin/tools/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_retrieve_tool(self):
        tool = Tool.objects.create(**VALID_TOOL_PAYLOAD)
        resp = self.client.get(f"/api/llm-admin/tools/{tool.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], VALID_TOOL_PAYLOAD["name"])

    def test_update_tool(self):
        tool = Tool.objects.create(**VALID_TOOL_PAYLOAD)
        resp = self.client.patch(f"/api/llm-admin/tools/{tool.id}/", {"description": "Updated"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["description"], "Updated")

    def test_delete_tool(self):
        tool = Tool.objects.create(**VALID_TOOL_PAYLOAD)
        resp = self.client.delete(f"/api/llm-admin/tools/{tool.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_llm_subagent_requires_llm_model(self):
        payload = {
            **VALID_TOOL_PAYLOAD,
            "name": "subagent-no-model",
            "tool_type": "llm_subagent",
            "implementation": "",
        }
        resp = self.client.post("/api/llm-admin/tools/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("llm_model", str(resp.data))

    def test_builtin_requires_implementation(self):
        payload = {**VALID_TOOL_PAYLOAD, "name": "no-impl", "implementation": ""}
        resp = self.client.post("/api/llm-admin/tools/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Tool Assignment tests
# ---------------------------------------------------------------------------

class ToolAssignmentTests(APITestCase):
    def setUp(self):
        self.admin = make_admin_user(email="assignadmin@test.com")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_access_token(self.admin)}")
        self.model = LLMModel.objects.create(**VALID_MODEL_PAYLOAD)
        self.tool = Tool.objects.create(**VALID_TOOL_PAYLOAD)

    def test_assign_tool_to_model(self):
        resp = self.client.post(
            f"/api/llm-admin/models/{self.model.id}/tools/",
            {"tool_id": str(self.tool.id), "priority": 1},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(LLMModelTool.objects.filter(llm_model=self.model, tool=self.tool).exists())

    def test_list_assigned_tools(self):
        LLMModelTool.objects.create(llm_model=self.model, tool=self.tool)
        resp = self.client.get(f"/api/llm-admin/models/{self.model.id}/tools/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    def test_duplicate_assignment_rejected(self):
        LLMModelTool.objects.create(llm_model=self.model, tool=self.tool)
        resp = self.client.post(
            f"/api/llm-admin/models/{self.model.id}/tools/",
            {"tool_id": str(self.tool.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remove_tool_from_model(self):
        LLMModelTool.objects.create(llm_model=self.model, tool=self.tool)
        resp = self.client.delete(
            f"/api/llm-admin/models/{self.model.id}/tools/{self.tool.id}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LLMModelTool.objects.filter(llm_model=self.model, tool=self.tool).exists())

    def test_remove_nonexistent_assignment_returns_404(self):
        resp = self.client.delete(
            f"/api/llm-admin/models/{self.model.id}/tools/{self.tool.id}/"
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Built-in Tool tests
# ---------------------------------------------------------------------------

class BuiltinToolTests(APITestCase):
    def test_calculator_basic(self):
        from llm_admin.builtin_tools.calculator import run
        self.assertEqual(run("2 + 2"), "4")
        self.assertEqual(run("10 / 4"), "2.5")
        self.assertEqual(run("2 ** 8"), "256")

    def test_calculator_division_by_zero(self):
        from llm_admin.builtin_tools.calculator import run
        result = run("1 / 0")
        self.assertIn("zero", result.lower())

    def test_calculator_rejects_unsafe_expressions(self):
        from llm_admin.builtin_tools.calculator import run
        result = run("__import__('os').system('echo hi')")
        self.assertIn("Error", result)

    def test_web_search_returns_string(self):
        from llm_admin.builtin_tools.web_search import run
        with patch("llm_admin.builtin_tools.web_search.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "Abstract": "Fever is an elevated body temperature.",
                "RelatedTopics": [{"Text": "Normal temp is 37°C."}],
            }
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp
            result = run("fever symptoms")
        self.assertIn("Fever", result)

    def test_patient_records_missing_patient(self):
        from llm_admin.builtin_tools.patient_records import run
        result = run("00000000-0000-0000-0000-000000000000")
        self.assertIn("No patient", result)


# ---------------------------------------------------------------------------
# Provider connection tests (mocked)
# ---------------------------------------------------------------------------

class ProviderConnectionTests(APITestCase):
    def _make_model(self, provider, **kwargs):
        defaults = {
            "name": f"{provider}_model",
            "provider": provider,
            "model_id": "test-model",
            "temperature": 0.7,
        }
        defaults.update(kwargs)
        return LLMModel(**defaults)

    def test_openai_complete_calls_api(self):
        from llm_admin.providers.openai_provider import OpenAIProviderClient
        with patch("openai.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content="Hello"))]
            )
            MockOpenAI.return_value = mock_client
            client = OpenAIProviderClient(self._make_model("openai"))
            result = client.complete([{"role": "user", "content": "Hi"}])
        self.assertEqual(result, "Hello")

    def test_ollama_test_connection_ok(self):
        from llm_admin.providers.ollama_provider import OllamaProviderClient
        with patch("llm_admin.providers.ollama_provider.requests.get") as mock_get:
            mock_get.return_value = MagicMock(ok=True)
            client = OllamaProviderClient(self._make_model("ollama", base_url="http://localhost:11434"))
            self.assertTrue(client.test_connection())

    def test_ollama_test_connection_fail(self):
        from llm_admin.providers.ollama_provider import OllamaProviderClient
        with patch("llm_admin.providers.ollama_provider.requests.get", side_effect=Exception("refused")):
            client = OllamaProviderClient(self._make_model("ollama", base_url="http://localhost:11434"))
            self.assertFalse(client.test_connection())


# ---------------------------------------------------------------------------
# Seeded tools tests
# ---------------------------------------------------------------------------

class SeedMigrationTests(APITestCase):
    """Verify that the 3 built-in tools are present after migrations."""

    def test_builtin_tools_seeded(self):
        names = list(Tool.objects.filter(
            name__in=["web_search", "calculator", "patient_records"]
        ).values_list("name", flat=True))
        self.assertIn("web_search", names)
        self.assertIn("calculator", names)
        self.assertIn("patient_records", names)
