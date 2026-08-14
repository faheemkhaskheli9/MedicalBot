from typing import Optional, TypedDict


class TriageState(TypedDict):
    conversation_history: list[dict]  # [{"role": "user"|"assistant", "content": str}]
    intent: str
    patient_name: str
    session_metadata: dict
    patient_id: str  # UUID string; empty if unavailable — used to fetch medical records
    bot_response: str
    agent_used: str
    risk_level: Optional[str]
    onboarding_complete: bool  # whether the patient's required onboarding slots are all filled
    onboarding_slots: dict  # {slot_key: extracted_value} collected so far this session
