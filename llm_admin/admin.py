from django.contrib import admin
from django.contrib import messages
from .models import LLMModel, Tool, LLMModelTool
from .providers import get_client


class LLMModelToolInline(admin.TabularInline):
    model = LLMModelTool
    extra = 1
    autocomplete_fields = ["tool"]


@admin.register(LLMModel)
class LLMModelAdmin(admin.ModelAdmin):
    list_display = ["name", "provider", "model_id", "is_active", "is_default", "created_at"]
    list_filter = ["provider", "is_active", "is_default"]
    search_fields = ["name", "model_id"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [LLMModelToolInline]
    actions = ["test_connection_action", "set_as_default_action"]

    def get_fields(self, request, obj=None):
        fields = [
            "id", "name", "provider", "model_id", "api_key",
            "base_url", "temperature", "max_tokens",
            "system_prompt_prefix", "is_active", "is_default",
            "created_at", "updated_at",
        ]
        return fields

    @admin.action(description="Test connection for selected models")
    def test_connection_action(self, request, queryset):
        for obj in queryset:
            try:
                client = get_client(obj)
                ok = client.test_connection()
                level = messages.SUCCESS if ok else messages.ERROR
                self.message_user(request, f"[{obj.name}] connection {'OK' if ok else 'FAILED'}", level)
            except Exception as exc:
                self.message_user(request, f"[{obj.name}] error: {exc}", messages.ERROR)

    @admin.action(description="Set selected model as default")
    def set_as_default_action(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one model to set as default.", messages.WARNING)
            return
        obj = queryset.first()
        obj.is_default = True
        obj.save()
        self.message_user(request, f"'{obj.name}' is now the default model.", messages.SUCCESS)


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ["name", "display_name", "tool_type", "is_active", "created_at"]
    list_filter = ["tool_type", "is_active"]
    search_fields = ["name", "display_name"]
    readonly_fields = ["id", "created_at"]
