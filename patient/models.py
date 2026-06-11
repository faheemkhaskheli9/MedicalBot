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
