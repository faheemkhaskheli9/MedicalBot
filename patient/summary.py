import json
import logging
from datetime import datetime, timezone

from .openai_client import get_openai_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a clinical documentation assistant. Given a chat transcript between a patient and "
    "a medical intake assistant, produce a concise structured clinical summary for the attending doctor.\n\n"
    "Respond with JSON only, using exactly this structure:\n"
    "{\n"
    '  "chief_complaint": "<one-sentence description of the main concern>",\n'
    '  "symptom_details": {\n'
    '    "location": "<body location or null>",\n'
    '    "duration": "<how long or null>",\n'
    '    "severity": <integer 1-10 or null>,\n'
    '    "character": "<description of symptom quality or null>",\n'
    '    "aggravating_factors": ["<factor>", ...],\n'
    '    "relieving_factors": ["<factor>", ...],\n'
    '    "associated_symptoms": ["<symptom>", ...]\n'
    "  },\n"
    '  "risk_level": "<routine|urgent|emergency>",\n'
    '  "recommended_action": "<what the doctor should do next>",\n'
    '  "notes_for_doctor": "<any additional clinical context worth highlighting>"\n'
    "}\n\n"
    "Base the summary solely on the conversation provided. "
    "If information was not discussed, use null or an empty list. "
    "Never invent clinical details not present in the conversation."
)


def generate_session_summary(conversation_history: list[dict], patient_name: str, patient_age: int) -> dict:
    """
    Generate a structured clinical summary from the conversation history.

    Returns a dict with the summary fields plus "generated_at".
    Raises on failure so the caller can return an appropriate error response.
    """
    transcript_lines = []
    for msg in conversation_history:
        role = "Patient" if msg["role"] == "user" else "MedicalBot"
        transcript_lines.append(f"{role}: {msg['content']}")
    transcript = "\n".join(transcript_lines)

    user_content = (
        f"Patient: {patient_name}, Age: {patient_age}\n\n"
        f"Conversation transcript:\n{transcript}"
    )

    client = get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    raw = json.loads(response.choices[0].message.content)

    # Normalise risk_level to valid choices
    valid_risk = {"routine", "urgent", "emergency"}
    if raw.get("risk_level") not in valid_risk:
        raw["risk_level"] = "routine"

    raw["generated_at"] = datetime.now(timezone.utc).isoformat()
    return raw
