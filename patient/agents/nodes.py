import json
import logging

from patient.llm_client import get_llm_provider

from .onboarding_slots import BLOOD_TYPE_CHOICES, next_missing_slot
from .state import TriageState

logger = logging.getLogger(__name__)

_INTAKE_SYSTEM = """You are MedicalBot, an AI medical intake assistant helping collect information before a doctor visit.

Patient name: {patient_name}

Your role:
- Gather symptom information through natural, empathetic conversation
- Ask ONE focused question per message — never ask multiple questions at once
- After you have gathered the main symptom, location, duration, severity (1–10), and any associated symptoms,
  provide a brief preliminary assessment and recommend next steps

If this appears to be the first message in the session, introduce yourself briefly, then ask about the patient's main concern.
Otherwise, continue from where the conversation left off.

IMPORTANT:
- You are NOT a doctor — never diagnose
- Always remind the patient to consult a qualified healthcare professional
- Keep responses concise and reassuring
- End every response with a single follow-up question (unless the assessment is complete)"""

_APPOINTMENT_SYSTEM = """You are MedicalBot, an AI medical assistant helping with appointment-related questions.

Patient name: {patient_name}

Help the patient:
- Understand what information and documents to prepare
- Know what to expect during a visit
- Describe their symptoms effectively to the doctor

For specific scheduling, direct them to contact the clinic directly.
Be helpful, professional, and concise."""

_MEDICATION_SYSTEM = """You are MedicalBot, an AI medical assistant answering general medication questions.

Patient name: {patient_name}

You may discuss:
- General information about how drug classes work
- Common side effects (remind them to check the package insert)
- General medication safety principles

NEVER:
- Prescribe medications or recommend dosages
- Override a doctor's prescription
- Make specific treatment recommendations

Always direct the patient to their doctor or pharmacist for their personal situation."""

_GENERAL_SYSTEM = """You are MedicalBot, an AI medical assistant.

Patient name: {patient_name}

Help the patient with their inquiry professionally and empathetically.
Always remind them that for medical advice they should consult a qualified healthcare professional."""


def _call_llm(system_prompt: str, conversation_history: list[dict]) -> str:
    return get_llm_provider().complete(
        [{"role": "system", "content": system_prompt}] + conversation_history
    ).strip()


def _get_patient_context(patient_id: str) -> str:
    """Fetch the patient's medical history and return it as a formatted context block."""
    if not patient_id:
        return ""
    try:
        from llm_admin.builtin_tools.patient_records import run
        result = run(patient_id)
        return f"\n\nPatient Medical Record:\n{result}"
    except Exception:
        logger.exception("Failed to fetch patient records for patient_id=%s", patient_id)
        return ""


def intake_node(state: TriageState) -> dict:
    try:
        prompt = _INTAKE_SYSTEM.format(patient_name=state["patient_name"]) + _get_patient_context(state.get("patient_id", ""))
        response = _call_llm(prompt, state["conversation_history"])
        return {"bot_response": response, "agent_used": "intake_agent"}
    except Exception:
        logger.exception("intake_node failed")
        return {
            "bot_response": (
                "I'm sorry, I'm having trouble processing your message right now. "
                "Please try again, or contact the clinic directly if this is urgent."
            ),
            "agent_used": "intake_agent",
        }


def appointment_node(state: TriageState) -> dict:
    try:
        prompt = _APPOINTMENT_SYSTEM.format(patient_name=state["patient_name"]) + _get_patient_context(state.get("patient_id", ""))
        response = _call_llm(prompt, state["conversation_history"])
        return {"bot_response": response, "agent_used": "appointment_agent"}
    except Exception:
        logger.exception("appointment_node failed")
        return {
            "bot_response": "I'm having trouble with your appointment request. Please contact the clinic directly.",
            "agent_used": "appointment_agent",
        }


def medication_node(state: TriageState) -> dict:
    try:
        prompt = _MEDICATION_SYSTEM.format(patient_name=state["patient_name"]) + _get_patient_context(state.get("patient_id", ""))
        response = _call_llm(prompt, state["conversation_history"])
        return {"bot_response": response, "agent_used": "medication_agent"}
    except Exception:
        logger.exception("medication_node failed")
        return {
            "bot_response": "I'm having trouble answering your medication question. Please consult your pharmacist or doctor.",
            "agent_used": "medication_agent",
        }


def general_node(state: TriageState) -> dict:
    try:
        prompt = _GENERAL_SYSTEM.format(patient_name=state["patient_name"]) + _get_patient_context(state.get("patient_id", ""))
        response = _call_llm(prompt, state["conversation_history"])
        return {"bot_response": response, "agent_used": "general_agent"}
    except Exception:
        logger.exception("general_node failed")
        return {
            "bot_response": "I'm sorry, I couldn't process your request. Please try again or contact the clinic.",
            "agent_used": "general_agent",
        }


_LAB_REPORT_SYSTEM = """You are MedicalBot, a medical lab results assistant.

Patient name: {patient_name}

Help the patient understand their lab results:
- Explain values in plain, jargon-free language
- Note which results appear outside typical reference ranges and what that may indicate
- Provide context (e.g., what a test measures, common reasons for abnormal values)
- Always recommend the patient consult their doctor for a full interpretation

NEVER diagnose. Never tell the patient what medication to take based on lab results.
Keep responses clear, reassuring, and concise."""


def lab_report_node(state: TriageState) -> dict:
    try:
        prompt = _LAB_REPORT_SYSTEM.format(patient_name=state["patient_name"]) + _get_patient_context(state.get("patient_id", ""))
        response = _call_llm(prompt, state["conversation_history"])
        return {"bot_response": response, "agent_used": "lab_report_agent"}
    except Exception:
        logger.exception("lab_report_node failed")
        return {
            "bot_response": "I'm having trouble explaining those lab results right now. Please consult your doctor directly.",
            "agent_used": "lab_report_agent",
        }


_ONBOARDING_EXTRACTION_SYSTEM = """You are extracting structured onboarding data from a patient's chat reply.

The patient was asked: "{question}"

Decide whether they actually answered this question. A decline like "none", "no allergies",
or "I'd rather not say" still counts as answered — only mark answered=false if the reply is
off-topic, evasive, or doesn't address the question at all.

{format_hint}

Respond with JSON only: {{"answered": true or false, "value": <extracted value, or null if answered is false>}}"""

_MULTI_FORMAT_HINT = (
    'Return "value" as a JSON list of short strings, e.g. ["penicillin", "peanuts"]. '
    "Use an empty list if the patient said they have none."
)
_SINGLE_FORMAT_HINT = 'Return "value" as a short plain string.'
_BLOOD_TYPE_FORMAT_HINT = (
    'Return "value" as exactly one of: ' + ", ".join(BLOOD_TYPE_CHOICES) + "."
)


def _extract_slot_answer(slot: dict, patient_reply: str) -> dict:
    """Ask the LLM whether patient_reply answers `slot`'s question, and if so, extract the value.

    Returns {"answered": bool, "value": Any}. Never raises — falls back to
    answered=False (which re-asks the same question) on any failure, since a
    silently-skipped required field is worse than asking twice.
    """
    if slot["key"] == "blood_type":
        format_hint = _BLOOD_TYPE_FORMAT_HINT
    elif slot["multi"]:
        format_hint = _MULTI_FORMAT_HINT
    else:
        format_hint = _SINGLE_FORMAT_HINT

    prompt = _ONBOARDING_EXTRACTION_SYSTEM.format(question=slot["question"], format_hint=format_hint)
    try:
        raw = get_llm_provider().complete([
            {"role": "system", "content": prompt},
            {"role": "user", "content": patient_reply},
        ])
        data = json.loads(raw)
        answered = bool(data.get("answered", False))
        value = data.get("value")

        if slot["multi"]:
            if not isinstance(value, list):
                value = [] if value in (None, "") else [str(value)]
            else:
                value = [str(v) for v in value]
        elif slot["key"] == "blood_type":
            value = value if value in BLOOD_TYPE_CHOICES else "unknown"
        elif value is not None:
            value = str(value)

        return {"answered": answered, "value": value}
    except Exception:
        logger.exception("onboarding slot extraction failed for slot=%s", slot["key"])
        return {"answered": False, "value": None}


def onboarding_node(state: TriageState) -> dict:
    """Deterministic slot-filling checklist for new-patient onboarding.

    Code (see onboarding_slots.next_missing_slot) owns the control flow —
    which question is next and when the checklist is complete. The LLM is
    only used to extract a value from the patient's last reply. This is
    intentionally NOT free-form generation: medical intake questions are
    fixed, reviewable text, not something re-phrased per call.
    """
    try:
        filled = dict(state.get("onboarding_slots") or {})
        history = state["conversation_history"]
        is_first_turn = len(history) <= 1

        if not is_first_turn:
            pending = next_missing_slot(filled)
            if pending is not None:
                latest_reply = history[-1]["content"]
                extraction = _extract_slot_answer(pending, latest_reply)
                if extraction["answered"]:
                    filled[pending["key"]] = extraction["value"]
                # else: leave the slot unfilled — the same question is re-asked below.

        remaining = next_missing_slot(filled)

        if remaining is None:
            response = (
                f"Thanks, {state['patient_name']} — that's everything I need for now. "
                "Your information has been saved for your care team. How can I help you today?"
            )
            return {
                "bot_response": response,
                "agent_used": "onboarding_agent",
                "onboarding_slots": filled,
                "onboarding_complete": True,
            }

        greeting = (
            f"Hi {state['patient_name']}, before we get started I need to collect a bit of "
            "background information so your care team has the full picture. "
            if is_first_turn else ""
        )
        return {
            "bot_response": f"{greeting}{remaining['question']}",
            "agent_used": "onboarding_agent",
            "onboarding_slots": filled,
            "onboarding_complete": False,
        }
    except Exception:
        logger.exception("onboarding_node failed")
        return {
            "bot_response": (
                "I'm sorry, I'm having trouble processing that right now. "
                "Could you try answering again, or contact the clinic directly?"
            ),
            "agent_used": "onboarding_agent",
            "onboarding_slots": state.get("onboarding_slots") or {},
            "onboarding_complete": False,
        }


def route_by_intent(state: TriageState) -> str:
    # Onboarding is mandatory and overrides normal intent routing until the
    # required checklist is complete — true emergencies never reach here at
    # all, since ChatMessageCreateView runs detect_emergency() before the
    # graph is invoked, for every message, onboarding or not.
    if not state.get("onboarding_complete", True):
        return "onboarding"

    intent = state["intent"]
    if intent in ("appointment_request",):
        return "appointment"
    if intent in ("medication_question",):
        return "medication"
    if intent in ("lab_report_question",):
        return "lab_report"
    if intent in ("billing_question", "hospital_info"):
        return "general"
    # symptom_check, follow_up, emergency (non-life-threatening), unknown → intake
    return "intake"
