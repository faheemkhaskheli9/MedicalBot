import uuid

from django.db import models

from users.models import User


GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other"),
    ("prefer_not_to_say", "Prefer not to say"),
]


class Patient(User):
    patient_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    phone = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = "patients"

    def __str__(self):
        return f"{self.name} ({self.email})"


class ChatSession(models.Model):
    SESSION_STATUS = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("abandoned", "Abandoned"),
    ]
    RISK_LEVELS = [
        ("routine", "Routine"),
        ("urgent", "Urgent"),
        ("emergency", "Emergency"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="chat_sessions")
    assigned_doctor = models.ForeignKey(
        "doctor.Doctor", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="assigned_sessions",
    )
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default="active")
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS, null=True, blank=True)
    current_agent = models.CharField(max_length=100, null=True, blank=True)
    session_metadata = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(null=True, blank=True)
    conversation_summary = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "chat_sessions"
        ordering = ["-started_at"]

    def __str__(self):
        return f"Session {self.id} — {self.patient.name} ({self.status})"


class Message(models.Model):
    SENDER_CHOICES = [
        ("patient", "Patient"),
        ("bot", "Bot"),
        ("system", "System"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    sender = models.CharField(max_length=20, choices=SENDER_CHOICES)
    content = models.TextField()
    agent_name = models.CharField(max_length=100, null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    is_summarized = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.sender}] {self.content[:60]}"


BLOOD_TYPE_CHOICES = [
    ("A+", "A+"), ("A-", "A-"),
    ("B+", "B+"), ("B-", "B-"),
    ("AB+", "AB+"), ("AB-", "AB-"),
    ("O+", "O+"), ("O-", "O-"),
    ("unknown", "Unknown"),
]


class MedicalHistory(models.Model):
    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name="medical_history")
    blood_type = models.CharField(max_length=10, choices=BLOOD_TYPE_CHOICES, default="unknown")
    chronic_conditions = models.JSONField(default=list, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    current_medications = models.JSONField(default=list, blank=True)
    emergency_contact_name = models.CharField(max_length=255, blank=True, default="")
    emergency_contact_phone = models.CharField(max_length=20, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "medical_histories"

    def __str__(self):
        return f"Medical history for {self.patient.name}"


class Appointment(models.Model):
    APPOINTMENT_STATUS = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="appointments")
    doctor = models.ForeignKey(
        "doctor.Doctor", on_delete=models.CASCADE, related_name="appointments"
    )
    session = models.ForeignKey(
        ChatSession, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="appointments",
    )
    scheduled_at = models.DateTimeField()
    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=APPOINTMENT_STATUS, default="pending")
    doctor_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "appointments"
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"Appointment [{self.patient.name} → Dr. {self.doctor.name}] on {self.scheduled_at:%Y-%m-%d %H:%M} ({self.status})"


class EmergencyEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="emergency_events")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="emergency_events")
    trigger_message = models.TextField()
    symptoms_detected = models.JSONField(default=list)
    guidance_given = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "emergency_events"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Emergency [{self.patient.name}] at {self.created_at:%Y-%m-%d %H:%M}"


class Recommendation(models.Model):
    """AI-generated follow-up recommendations based on the session clinical summary."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(
        ChatSession, on_delete=models.CASCADE, related_name="recommendation"
    )
    content = models.JSONField()
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recommendations"

    def __str__(self):
        return f"Recommendation for session {self.session_id}"
