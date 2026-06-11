from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(UserAdmin):
    list_display = ["patient_id", "name", "email", "phone", "age", "gender", "date_joined"]
    search_fields = ["name", "email", "phone"]
    ordering = ["-date_joined"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("name", "age", "gender", "phone")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "age", "gender", "phone", "password1", "password2"),
            },
        ),
    )
