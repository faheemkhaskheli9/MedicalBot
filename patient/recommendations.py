import json
import logging

from .llm_client import get_llm_provider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a clinical decision-support AI. Based on the provided clinical summary and "
    "patient medical history, generate follow-up recommendations for the patient.\n\n"
    "Respond ONLY with valid JSON in exactly this shape:\n"
    "{\n"
    '  "tests_recommended": ["<test>", ...],\n'
    '  "specialist_referral": "<specialist type or null>",\n'
    '  "lifestyle_advice": ["<advice>", ...],\n'
    '  "urgency": "<immediate|within 24 hours|within 1 week|routine follow-up>",\n'
    '  "red_flags_to_watch": ["<symptom to watch for>", ...]\n'
    "}\n\n"
    "Base recommendations solely on the information provided. "
    "Do NOT diagnose. Always note that these are AI-generated suggestions for patient guidance only."
)


def generate_recommendations(session, patient) -> dict:
    """
    Generate follow-up recommendations from session clinical summary + patient medical history.
    Raises ValueError if session has no clinical summary.
    Raises on LLM failure.
    """
    if not session.summary:
        raise ValueError("Session has no clinical summary. Generate a summary first.")

    history_block = ""
    try:
        history = patient.medical_history
        parts = []
        if history.blood_type and history.blood_type != "unknown":
            parts.append(f"Blood type: {history.blood_type}")
        if history.chronic_conditions:
            parts.append(f"Chronic conditions: {history.chronic_conditions}")
        if history.allergies:
            parts.append(f"Allergies: {history.allergies}")
        if history.current_medications:
            parts.append(f"Current medications: {history.current_medications}")
        if parts:
            history_block = "\n\nPatient Medical History:\n" + "\n".join(parts)
    except Exception:
        pass

    user_content = (
        f"Clinical Summary:\n{json.dumps(session.summary, indent=2)}"
        f"{history_block}"
    )

    result = get_llm_provider().complete([
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ])

    return json.loads(result)
