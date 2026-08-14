import logging

from llm_admin.providers.base import ProviderClient

logger = logging.getLogger(__name__)


class _OpenAISingletonAdapter(ProviderClient):
    """Thin adapter wrapping the existing OpenAI singleton to satisfy ProviderClient."""

    def __init__(self, client):
        self._client = client

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        response = self._client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        return response.choices[0].message.content or ""

    def test_connection(self) -> bool:
        return True


def get_llm_provider() -> ProviderClient:
    """
    Return a ProviderClient for the active default LLMModel configured in llm_admin.
    Falls back to the env-var OpenAI singleton if no default model is configured.
    """
    try:
        from llm_admin.models import LLMModel
        from llm_admin.providers import get_client

        model = LLMModel.objects.filter(is_default=True, is_active=True).first()
        if model:
            return get_client(model)
    except Exception:
        logger.exception("Failed to load default LLM model from llm_admin, using fallback")

    from patient.openai_client import get_openai_client
    return _OpenAISingletonAdapter(get_openai_client())
