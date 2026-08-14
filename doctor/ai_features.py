import json
import logging

from patient.llm_client import get_llm_provider

logger = logging.getLogger(__name__)

# ── Differential Diagnosis ────────────────────────────────────────────────────

_DIAGNOSIS_SYSTEM = (
    "You are a clinical decision-support AI assisting a doctor (NOT replacing them). "
    "Based on the patient's chat transcript and medical history, suggest a differential diagnosis.\n\n"
    "Respond ONLY with valid JSON in exactly this shape:\n"
    "{\n"
    '  "differentials": [\n'
    '    {"condition": "<name>", "likelihood": "high|moderate|low", "reasoning": "<brief explanation>"},\n'
    "    ...\n"
    "  ],\n"
    '  "recommended_workup": ["<test or investigation>", ...],\n'
    '  "caution": "AI-generated suggestions only. Clinical judgment of the treating physician is required."\n'
    "}\n\n"
    "Limit differentials to the 3-5 most clinically relevant. "
    "Never make definitive diagnoses. Always include the caution disclaimer."
)


def generate_differential_diagnosis(session, doctor) -> dict:
    """
    Generate a differential diagnosis from the session transcript + patient medical history.
    Raises ValueError if session has no messages.
    """
    messages = list(session.messages.order_by("created_at"))
    if not messages:
        raise ValueError("Session has no messages to analyse.")

    transcript = "\n".join(
        f"{'PATIENT' if m.sender == 'patient' else 'BOT'}: {m.content}"
        for m in messages
    )

    history_block = ""
    try:
        from llm_admin.builtin_tools.patient_records import run
        history_block = f"\n\nPatient Medical Record:\n{run(str(session.patient.patient_id))}"
    except Exception:
        pass

    user_content = (
        f"Doctor specialization: {doctor.specialization}\n\n"
        f"Chat transcript:\n{transcript}"
        f"{history_block}"
    )

    result = get_llm_provider().complete([
        {"role": "system", "content": _DIAGNOSIS_SYSTEM},
        {"role": "user", "content": user_content},
    ])
    return json.loads(result)


# ── SOAP Note Draft ───────────────────────────────────────────────────────────

_SOAP_SYSTEM = (
    "You are a clinical documentation assistant. Based on the provided clinical summary, "
    "write a SOAP note draft for the attending doctor to review and edit.\n\n"
    "Format the note clearly with these four sections:\n"
    "SUBJECTIVE: What the patient reports (chief complaint, symptoms, history of present illness)\n"
    "OBJECTIVE: Observable/measurable findings (from the summary — note if no physical exam was done)\n"
    "ASSESSMENT: Clinical impression based on the available information\n"
    "PLAN: Recommended next steps\n\n"
    "Mark this clearly as a DRAFT requiring physician review. "
    "Base it only on the provided summary — do not invent findings."
)


def generate_soap_draft(session) -> str:
    """
    Generate a SOAP note draft from the session clinical summary.
    Raises ValueError if session has no clinical summary.
    """
    if not session.summary:
        raise ValueError("Session has no clinical summary. Generate a summary first.")

    user_content = f"Clinical summary:\n{json.dumps(session.summary, indent=2)}"
    return get_llm_provider().complete([
        {"role": "system", "content": _SOAP_SYSTEM},
        {"role": "user", "content": user_content},
    ])


# ── Drug Interaction Check ────────────────────────────────────────────────────

_INTERACTION_SYSTEM = (
    "You are a pharmacology decision-support AI. "
    "Check the proposed medications for interactions with each other and with the patient's current medications.\n\n"
    "Respond ONLY with valid JSON in exactly this shape:\n"
    "{\n"
    '  "interactions_found": [\n'
    '    {"drugs": ["<drug1>", "<drug2>"], "severity": "high|moderate|low", "explanation": "<brief explanation>"},\n'
    "    ...\n"
    "  ],\n"
    '  "safe_to_prescribe": true or false,\n'
    '  "caution": "AI check only. Consult a clinical pharmacist or prescribing guidelines before finalising."\n'
    "}\n\n"
    "If no interactions are found, return an empty interactions_found list and safe_to_prescribe: true."
)


def check_drug_interactions(new_medications: list, patient_id: str) -> dict:
    """
    Check new_medications for interactions with each other and with patient's current medications.
    patient_id is the patient UUID string.
    """
    current_medications = []
    try:
        from patient.models import Patient
        patient = Patient.objects.filter(patient_id=patient_id).first()
        if patient:
            history = getattr(patient, "medical_history", None)
            if history and history.current_medications:
                current_medications = history.current_medications
    except Exception:
        pass

    user_content = (
        f"New medications to prescribe: {json.dumps(new_medications)}\n"
        f"Patient's current medications: {json.dumps(current_medications) if current_medications else 'None on record'}"
    )

    result = get_llm_provider().complete([
        {"role": "system", "content": _INTERACTION_SYSTEM},
        {"role": "user", "content": user_content},
    ])
    return json.loads(result)


# ── Cross-Session Patient Summary ─────────────────────────────────────────────

_CROSS_SUMMARY_SYSTEM = (
    "You are a medical data analyst reviewing a patient's health history across multiple chat sessions. "
    "Identify recurring complaints, trends over time, concerning patterns, and any gaps in care. "
    "Be concise (5-8 sentences). Do NOT diagnose. Focus on patterns a doctor should be aware of."
)


def generate_cross_session_summary(patient, sessions_with_summaries: list) -> dict:
    """
    Aggregate session summaries and optionally call LLM for trend analysis.
    Returns {session_count, sessions, trend_analysis}.
    """
    session_entries = []
    for s in sessions_with_summaries:
        session_entries.append({
            "session_id": str(s.id),
            "date": s.started_at.isoformat(),
            "risk_level": s.risk_level,
            "chief_complaint": s.summary.get("chief_complaint"),
            "recommended_action": s.summary.get("recommended_action"),
            "notes_for_doctor": s.summary.get("notes_for_doctor"),
        })

    trend_analysis = None
    if session_entries:
        try:
            trend_analysis = get_llm_provider().complete([
                {"role": "system", "content": _CROSS_SUMMARY_SYSTEM},
                {"role": "user", "content": f"Patient history:\n{json.dumps(session_entries, indent=2)}"},
            ])
        except Exception:
            logger.exception("Cross-session trend analysis failed for patient %s", patient.patient_id)

    dates = [s.started_at.isoformat() for s in sessions_with_summaries]
    return {
        "patient_name": patient.name,
        "session_count": len(session_entries),
        "date_range": {"from": dates[0], "to": dates[-1]} if dates else None,
        "sessions": session_entries,
        "trend_analysis": trend_analysis,
    }
