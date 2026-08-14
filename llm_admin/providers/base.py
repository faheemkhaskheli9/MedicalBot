from abc import ABC, abstractmethod


class ProviderClient(ABC):
    """Abstract interface every LLM provider must implement."""

    @abstractmethod
    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        """Return the assistant's reply text."""
        ...

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if the provider is reachable and the key is valid."""
        ...
