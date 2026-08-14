import uuid

from django.db import models

from users.models import User


SPECIALIZATION_CHOICES = [
    ("general_practice", "General Practice"),
    ("cardiology", "Cardiology"),
    ("neurology", "Neurology"),
    ("pediatrics", "Pediatrics"),
    ("emergency_medicine", "Emergency Medicine"),
    ("internal_medicine", "Internal Medicine"),
    ("psychiatry", "Psychiatry"),
    ("other", "Other"),
]


class Doctor(User):
    name = models.CharField(max_length=255)
    specialization = models.CharField(max_length=50, choices=SPECIALIZATION_CHOICES, default="general_practice")
    license_number = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "doctors"

    def __str__(self):
        return f"Dr. {self.name} ({self.specialization})"


class Prescription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="prescriptions")
    session = models.ForeignKey(
        "patient.ChatSession", on_delete=models.CASCADE, related_name="prescriptions"
    )
    medications = models.JSONField(default=list)
    instructions = models.TextField(blank=True, default="")
    follow_up_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prescriptions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Prescription by Dr. {self.doctor.name} for session {self.session_id}"


class DoctorNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        "patient.ChatSession", on_delete=models.CASCADE, related_name="doctor_notes"
    )
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="notes")
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "doctor_notes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note by Dr. {self.doctor.name} on session {self.session_id}"
