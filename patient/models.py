import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class PatientManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other"),
    ("prefer_not_to_say", "Prefer not to say"),
]


class Patient(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    phone = models.CharField(max_length=20, unique=True)
    patient_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    objects = PatientManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "phone", "age", "gender"]

    class Meta:
        db_table = "patients"

    def __str__(self):
        return f"{self.name} ({self.email})"
