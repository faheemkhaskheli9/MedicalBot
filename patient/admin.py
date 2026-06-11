from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["patient_id", "name", "email", "phone", "age", "gender", "date_joined"]
    search_fields = ["name", "email", "phone"]
    ordering = ["-date_joined"]
    readonly_fields = ["patient_id", "date_joined"]
