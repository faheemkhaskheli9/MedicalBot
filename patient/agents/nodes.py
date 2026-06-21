import logging

from patient.openai_client import get_openai_client

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


def _call_openai(system_prompt: str, conversation_history: list[dict]) -> str:
    client = get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system_prompt}] + conversation_history,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def intake_node(state: TriageState) -> dict:
    try:
        prompt = _INTAKE_SYSTEM.format(patient_name=state["patient_name"])
        response = _call_openai(prompt, state["conversation_history"])
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
        prompt = _APPOINTMENT_SYSTEM.format(patient_name=state["patient_name"])
        response = _call_openai(prompt, state["conversation_history"])
        return {"bot_response": response, "agent_used": "appointment_agent"}
    except Exception:
        logger.exception("appointment_node failed")
        return {
            "bot_response": "I'm having trouble with your appointment request. Please contact the clinic directly.",
            "agent_used": "appointment_agent",
        }


def medication_node(state: TriageState) -> dict:
    try:
        prompt = _MEDICATION_SYSTEM.format(patient_name=state["patient_name"])
        response = _call_openai(prompt, state["conversation_history"])
        return {"bot_response": response, "agent_used": "medication_agent"}
    except Exception:
        logger.exception("medication_node failed")
        return {
            "bot_response": "I'm having trouble answering your medication question. Please consult your pharmacist or doctor.",
            "agent_used": "medication_agent",
        }


def general_node(state: TriageState) -> dict:
    try:
        prompt = _GENERAL_SYSTEM.format(patient_name=state["patient_name"])
        response = _call_openai(prompt, state["conversation_history"])
        return {"bot_response": response, "agent_used": "general_agent"}
    except Exception:
        logger.exception("general_node failed")
        return {
            "bot_response": "I'm sorry, I couldn't process your request. Please try again or contact the clinic.",
            "agent_used": "general_agent",
        }


def route_by_intent(state: TriageState) -> str:
    intent = state["intent"]
    if intent in ("appointment_request",):
        return "appointment"
    if intent in ("medication_question",):
        return "medication"
    if intent in ("lab_report_question", "billing_question", "hospital_info"):
        return "general"
    # symptom_check, follow_up, emergency (non-life-threatening), unknown → intake
    return "intake"
