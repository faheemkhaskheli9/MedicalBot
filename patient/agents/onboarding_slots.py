"""Slot registry for the patient onboarding flow.

Onboarding is a deterministic checklist, not a free-form LLM conversation:
this module decides *what* gets asked and *when the checklist is done*.
The LLM (see ``onboarding_node`` in ``nodes.py``) is only trusted to extract
a structured value out of the patient's free-text reply to a given
question — it never decides which question comes next. That guarantees
every required field is asked exactly once and none are silently skipped,
even across many turns and even if the model gets chatty.
"""

# Order matters: required slots are asked first, in this order, then the
# optional ones. Keep in sync with patient.models.MedicalHistory.
ONBOARDING_SLOTS = [
    {
        "key": "chronic_conditions",
        "question": (
            "Do you have any chronic conditions, such as diabetes, hypertension, "
            "or asthma? If none, just say so."
        ),
        "required": True,
        "multi": True,
    },
    {
        "key": "allergies",
        "question": (
            "Do you have any known allergies, especially to medications? "
            "If none, just say so."
        ),
        "required": True,
        "multi": True,
    },
    {
        "key": "current_medications",
        "question": (
            "Are you currently taking any medications, including over-the-counter "
            "drugs or supplements? If none, just say so."
        ),
        "required": True,
        "multi": True,
    },
    {
        "key": "emergency_contact_name",
        "question": "Who should we contact in case of an emergency? Please give their full name.",
        "required": True,
        "multi": False,
    },
    {
        "key": "emergency_contact_phone",
        "question": "What's the best phone number to reach that person?",
        "required": True,
        "multi": False,
    },
    {
        "key": "blood_type",
        "question": (
            "Do you know your blood type (e.g. O+, A-)? It's fine to skip this "
            "if you don't know."
        ),
        "required": False,
        "multi": False,
    },
]

REQUIRED_SLOT_KEYS = [slot["key"] for slot in ONBOARDING_SLOTS if slot["required"]]
BLOOD_TYPE_CHOICES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"]


def get_slot(key: str) -> dict | None:
    for slot in ONBOARDING_SLOTS:
        if slot["key"] == key:
            return slot
    return None


def next_missing_slot(filled: dict) -> dict | None:
    """Return the next slot that still needs an answer, or None once every
    required slot has an entry in ``filled`` (optional slots are asked last,
    and skipped once the patient has been offered them once)."""
    for slot in ONBOARDING_SLOTS:
        if slot["required"] and slot["key"] not in filled:
            return slot
    for slot in ONBOARDING_SLOTS:
        if not slot["required"] and slot["key"] not in filled:
            return slot
    return None


def is_required_complete(filled: dict) -> bool:
    return all(key in filled for key in REQUIRED_SLOT_KEYS)
