import os
from .base import ProviderClient


class GoogleProviderClient(ProviderClient):
    def __init__(self, llm_model):
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise ImportError("Install 'google-generativeai' to use the Google provider.") from exc

        api_key = llm_model.api_key or os.environ.get("GOOGLE_API_KEY", "")
        genai.configure(api_key=api_key)
        self._genai = genai
        self._model_id = llm_model.model_id
        self._temperature = llm_model.temperature
        self._max_tokens = llm_model.max_tokens

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        gen_config = {"temperature": self._temperature}
        if self._max_tokens:
            gen_config["max_output_tokens"] = self._max_tokens

        model = self._genai.GenerativeModel(self._model_id, generation_config=gen_config)

        # Convert messages: extract system prompt, convert to Gemini history format
        system_parts = []
        history = []
        for m in messages:
            if m["role"] == "system":
                system_parts.append(m["content"])
            elif m["role"] == "user":
                history.append({"role": "user", "parts": [m["content"]]})
            elif m["role"] == "assistant":
                history.append({"role": "model", "parts": [m["content"]]})

        # Last user message becomes the actual prompt
        if history and history[-1]["role"] == "user":
            last_user = history.pop()
            prompt = last_user["parts"][0]
        else:
            prompt = ""

        chat = model.start_chat(history=history)
        response = chat.send_message(prompt)
        return response.text or ""

    def test_connection(self) -> bool:
        try:
            model = self._genai.GenerativeModel(self._model_id)
            model.generate_content("ping")
            return True
        except Exception:
            return False
