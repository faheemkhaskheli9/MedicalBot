import json
import logging

from .llm_client import get_llm_provider

logger = logging.getLogger(__name__)

_EMERGENCY_KEYWORDS = [
    "chest pain", "heart attack", "stroke", "unconscious", "not breathing",
    "severe bleeding", "seizure", "suicidal", "want to die", "kill myself",
    "anaphylaxis", "allergic reaction", "can't breathe", "cannot breathe",
    "shortness of breath", "difficulty breathing", "pregnancy emergency",
    "miscarriage", "premature labor", "high fever infant", "baby fever",
    "choking", "overdose", "poisoning",
]

_SYSTEM_PROMPT = (
    "You are an emergency medical triage AI. Your ONLY job is to determine if a patient "
    "message describes a life-threatening medical emergency.\n\n"
    "Emergency conditions include (but are not limited to):\n"
    "- Chest pain or heart attack symptoms (pressure, tightness, pain radiating to arm/jaw)\n"
    "- Stroke symptoms (facial drooping, arm weakness, speech difficulty, sudden confusion)\n"
    "- Severe shortness of breath or inability to breathe\n"
    "- Loss of consciousness or unresponsiveness\n"
    "- Severe uncontrolled bleeding\n"
    "- Seizures\n"
    "- Suicidal thoughts or intent to harm oneself\n"
    "- Severe allergic reaction (anaphylaxis): throat swelling, difficulty breathing\n"
    "- Pregnancy emergency: heavy bleeding, severe abdominal pain, premature labour\n"
    "- High fever in infant under 3 months, or very high fever with stiff neck\n"
    "- Severe burns, poisoning, or overdose\n\n"
    "Be cautious — when in doubt, classify as emergency (false negatives are dangerous).\n\n"
    "Respond with JSON only:\n"
    '{"is_emergency": true or false, "symptoms_detected": ["<symptom>", ...], "confidence": <0–1 float>}\n'
    "If is_emergency is false, symptoms_detected must be an empty list."
)

EMERGENCY_GUIDANCE = (
    "EMERGENCY ALERT: Your message indicates a possible medical emergency.\n\n"
    "Please take action NOW:\n"
    "1. Call emergency services (911) immediately, or ask someone nearby to call.\n"
    "2. Go to the nearest Emergency Room if you can do so safely.\n"
    "3. Do NOT wait for further responses from this chat.\n\n"
    "If you cannot call, show this screen to someone nearby and ask them to call 911 for you.\n\n"
    "This chat system cannot replace emergency care. Please seek immediate help.\n\n"
    "_If you are in immediate danger, call 911 now._"
)


def _keyword_fallback(message_content: str) -> dict:
    """Keyword-based fallback when OpenAI is unavailable."""
    lower = message_content.lower()
    found = [kw for kw in _EMERGENCY_KEYWORDS if kw in lower]
    return {
        "is_emergency": bool(found),
        "symptoms_detected": found,
        "confidence": 0.8 if found else 0.0,
    }


def detect_emergency(message_content: str) -> dict:
    """
    Detect life-threatening emergency symptoms in message_content using OpenAI.
    Returns {"is_emergency": bool, "symptoms_detected": list[str], "confidence": float}.
    Falls back to keyword matching if OpenAI is unavailable to avoid missing emergencies.
    """
    try:
        result = get_llm_provider().complete([
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": message_content},
        ])
        raw = json.loads(result)
        is_emergency = bool(raw.get("is_emergency", False))
        symptoms = raw.get("symptoms_detected", [])
        if not isinstance(symptoms, list):
            symptoms = []
        confidence = float(raw.get("confidence", 0.0))
        return {"is_emergency": is_emergency, "symptoms_detected": symptoms, "confidence": confidence}
    except Exception:
        logger.exception("Emergency detection via OpenAI failed, falling back to keyword match")
        return _keyword_fallback(message_content)
