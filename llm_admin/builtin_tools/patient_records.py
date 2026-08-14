PARAMETERS_SCHEMA = {
    "type": "object",
    "properties": {
        "patient_id": {
            "type": "string",
            "description": "UUID of the patient whose medical history to retrieve",
        },
    },
    "required": ["patient_id"],
}


def run(patient_id: str) -> str:
    """Return the patient's medical history fields as a formatted string."""
    try:
        from patient.models import MedicalHistory, Patient

        patient = Patient.objects.filter(patient_id=patient_id).first()
        if not patient:
            return f"No patient found with id={patient_id}"

        history = MedicalHistory.objects.filter(patient=patient).first()
        if not history:
            return "No medical history on record for this patient."

        lines = [
            f"Blood type: {history.blood_type or 'unknown'}",
            f"Chronic conditions: {history.chronic_conditions or 'none'}",
            f"Allergies: {history.allergies or 'none'}",
            f"Current medications: {history.medications or 'none'}",
        ]
        if history.emergency_contact:
            lines.append(f"Emergency contact: {history.emergency_contact}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error retrieving patient records: {exc}"
