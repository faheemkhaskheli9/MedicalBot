from .base import ProviderClient
from .openai_provider import OpenAIProviderClient
from .anthropic_provider import AnthropicProviderClient
from .google_provider import GoogleProviderClient
from .ollama_provider import OllamaProviderClient


def get_client(llm_model) -> ProviderClient:
    """Return the appropriate provider client for the given LLMModel instance."""
    mapping = {
        "openai": OpenAIProviderClient,
        "anthropic": AnthropicProviderClient,
        "google": GoogleProviderClient,
        "ollama": OllamaProviderClient,
    }
    cls = mapping.get(llm_model.provider)
    if cls is None:
        raise ValueError(f"Unknown provider: {llm_model.provider!r}")
    return cls(llm_model)


__all__ = [
    "ProviderClient",
    "OpenAIProviderClient",
    "AnthropicProviderClient",
    "GoogleProviderClient",
    "OllamaProviderClient",
    "get_client",
]
