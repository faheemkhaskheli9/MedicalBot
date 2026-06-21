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
