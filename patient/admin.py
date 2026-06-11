from django.contrib import admin

from .models import ChatSession, Message, Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["patient_id", "name", "email", "phone", "age", "gender", "date_joined"]
    search_fields = ["name", "email", "phone"]
    ordering = ["-date_joined"]
    readonly_fields = ["patient_id", "date_joined"]


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["id", "sender", "content", "agent_name", "created_at"]
    can_delete = False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ["id", "patient", "status", "risk_level", "current_agent", "started_at", "ended_at"]
    list_filter = ["status", "risk_level"]
    search_fields = ["patient__name", "patient__email"]
    ordering = ["-started_at"]
    readonly_fields = ["id", "started_at"]
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "sender", "agent_name", "content_preview", "created_at"]
    list_filter = ["sender", "agent_name"]
    search_fields = ["content"]
    readonly_fields = ["id", "created_at"]

    def content_preview(self, obj):
        return obj.content[:80]
    content_preview.short_description = "Content"
