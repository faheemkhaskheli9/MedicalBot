from langgraph.graph import END, START, StateGraph

from .nodes import appointment_node, general_node, intake_node, lab_report_node, medication_node, route_by_intent
from .state import TriageState


def _build_graph():
    builder = StateGraph(TriageState)

    builder.add_node("intake", intake_node)
    builder.add_node("appointment", appointment_node)
    builder.add_node("medication", medication_node)
    builder.add_node("general", general_node)
    builder.add_node("lab_report", lab_report_node)

    builder.add_conditional_edges(
        START,
        route_by_intent,
        {
            "intake": "intake",
            "appointment": "appointment",
            "medication": "medication",
            "general": "general",
            "lab_report": "lab_report",
        },
    )

    builder.add_edge("intake", END)
    builder.add_edge("appointment", END)
    builder.add_edge("medication", END)
    builder.add_edge("general", END)
    builder.add_edge("lab_report", END)

    return builder.compile()


triage_graph = _build_graph()
