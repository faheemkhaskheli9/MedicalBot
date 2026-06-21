import logging
from typing import Optional

from .graph import triage_graph
from .state import TriageState

logger = logging.getLogger(__name__)


def run_triage_graph(
    conversation_history: list[dict],
    intent: str,
    patient_name: str,
    session_metadata: dict,
) -> dict:
    """
    Run the LangGraph triage orchestrator for a single patient message.

    Returns:
        {
            "bot_response": str,
            "agent_used": str,
            "risk_level": str | None,
        }
    """
    initial_state: TriageState = {
        "conversation_history": conversation_history,
        "intent": intent,
        "patient_name": patient_name,
        "session_metadata": session_metadata,
        "bot_response": "",
        "agent_used": "",
        "risk_level": None,
    }
    try:
        result = triage_graph.invoke(initial_state)
        return {
            "bot_response": result["bot_response"],
            "agent_used": result["agent_used"],
            "risk_level": result.get("risk_level"),
        }
    except Exception:
        logger.exception("triage_graph.invoke failed")
        return {
            "bot_response": (
                "I'm sorry, I'm experiencing technical difficulties. "
                "Please try again or contact the clinic directly."
            ),
            "agent_used": "fallback",
            "risk_level": None,
        }
