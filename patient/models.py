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
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default="active")
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS, null=True, blank=True)
    current_agent = models.CharField(max_length=100, null=True, blank=True)
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.sender}] {self.content[:60]}"
