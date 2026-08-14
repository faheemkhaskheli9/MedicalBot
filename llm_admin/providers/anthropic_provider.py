import os
from .base import ProviderClient


class AnthropicProviderClient(ProviderClient):
    def __init__(self, llm_model):
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError("Install the 'anthropic' package to use the Anthropic provider.") from exc

        api_key = llm_model.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model_id = llm_model.model_id
        self._temperature = llm_model.temperature
        self._max_tokens = llm_model.max_tokens or 1024

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        # Anthropic separates system prompt from messages
        system_prompt = None
        filtered = []
        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            else:
                filtered.append(m)

        kwargs = dict(
            model=self._model_id,
            max_tokens=self._max_tokens,
            messages=filtered,
            temperature=self._temperature,
        )
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            # Convert OpenAI-style tools to Anthropic format
            kwargs["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get("parameters", {}),
                }
                for t in tools
            ]

        response = self._client.messages.create(**kwargs)
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    def test_connection(self) -> bool:
        try:
            self._client.messages.create(
                model=self._model_id,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False
