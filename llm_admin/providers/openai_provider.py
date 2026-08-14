import os
from .base import ProviderClient


class OpenAIProviderClient(ProviderClient):
    def __init__(self, llm_model):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("Install the 'openai' package to use the OpenAI provider.") from exc

        api_key = llm_model.api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = OpenAI(api_key=api_key)
        self._model_id = llm_model.model_id
        self._temperature = llm_model.temperature
        self._max_tokens = llm_model.max_tokens

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        kwargs = dict(model=self._model_id, messages=messages, temperature=self._temperature)
        if self._max_tokens:
            kwargs["max_tokens"] = self._max_tokens
        if tools:
            kwargs["tools"] = tools
        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def test_connection(self) -> bool:
        try:
            self._client.models.retrieve(self._model_id)
            return True
        except Exception:
            return False
