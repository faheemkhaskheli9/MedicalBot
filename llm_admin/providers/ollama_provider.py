import requests
from .base import ProviderClient


class OllamaProviderClient(ProviderClient):
    def __init__(self, llm_model):
        self._base_url = (llm_model.base_url or "http://localhost:11434").rstrip("/")
        self._model_id = llm_model.model_id
        self._temperature = llm_model.temperature
        self._max_tokens = llm_model.max_tokens

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        payload = {
            "model": self._model_id,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self._temperature},
        }
        if self._max_tokens:
            payload["options"]["num_predict"] = self._max_tokens

        resp = requests.post(f"{self._base_url}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    def test_connection(self) -> bool:
        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=5)
            return resp.ok
        except Exception:
            return False
