import json
import logging
import os

logger = logging.getLogger(__name__)

SUPPORTED_INTENTS = [
    "symptom_check",
    "appointment_request",
    "lab_report_question",
    "medication_question",
    "billing_question",
    "hospital_info",
    "follow_up",
    "emergency",
    "unknown",
]

_SYSTEM_PROMPT = (
    "You are a medical triage assistant. Classify the patient message into exactly one of these intents:\n"
    + ", ".join(SUPPORTED_INTENTS)
    + "\n\nRules:\n"
    "- Use 'emergency' for life-threatening or urgent danger situations.\n"
    "- Use 'unknown' when the message does not fit any other category.\n"
    "- Never use an intent outside the list above.\n\n"
    'Respond with JSON only: {"intent": "<intent>", "confidence": <float between 0 and 1>}'
)


def detect_intent(message_content: str) -> dict:
    """
    Classify message_content into one of SUPPORTED_INTENTS using OpenAI.
    Returns {"intent": str, "confidence": float}.
    Falls back to {"intent": "unknown", "confidence": 0.0} on any error.
    """
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": message_content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = json.loads(response.choices[0].message.content)
        intent = raw.get("intent", "unknown")
        if intent not in SUPPORTED_INTENTS:
            intent = "unknown"
        confidence = float(raw.get("confidence", 0.0))
        return {"intent": intent, "confidence": confidence}
    except Exception:
        logger.exception("Intent detection failed, falling back to 'unknown'")
        return {"intent": "unknown", "confidence": 0.0}
