from typing import Optional, TypedDict


class TriageState(TypedDict):
    conversation_history: list[dict]  # [{"role": "user"|"assistant", "content": str}]
    intent: str
    patient_name: str
    session_metadata: dict
    bot_response: str
    agent_used: str
    risk_level: Optional[str]
