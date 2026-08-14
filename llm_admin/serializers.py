from rest_framework import serializers
from .models import LLMModel, Tool, LLMModelTool


class ToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool
        fields = [
            "id", "name", "display_name", "description",
            "tool_type", "implementation", "llm_model",
            "parameters_schema", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        tool_type = attrs.get("tool_type", getattr(self.instance, "tool_type", None))
        llm_model = attrs.get("llm_model", getattr(self.instance, "llm_model", None))
        implementation = attrs.get("implementation", getattr(self.instance, "implementation", ""))

        if tool_type == Tool.TYPE_LLM_SUBAGENT and not llm_model:
            raise serializers.ValidationError(
                {"llm_model": "An LLM model must be selected for llm_subagent tools."}
            )
        if tool_type in (Tool.TYPE_BUILTIN, Tool.TYPE_CUSTOM) and not implementation:
            raise serializers.ValidationError(
                {"implementation": "An implementation path is required for built_in/custom tools."}
            )
        return attrs


class LLMModelToolSerializer(serializers.ModelSerializer):
    tool = ToolSerializer(read_only=True)
    tool_id = serializers.PrimaryKeyRelatedField(
        queryset=Tool.objects.all(), source="tool", write_only=True
    )

    class Meta:
        model = LLMModelTool
        fields = ["id", "tool", "tool_id", "priority"]
        read_only_fields = ["id"]


class LLMModelSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(
        max_length=500, write_only=True, required=False, allow_blank=True
    )
    tool_assignments = LLMModelToolSerializer(many=True, read_only=True)

    class Meta:
        model = LLMModel
        fields = [
            "id", "name", "provider", "model_id",
            "api_key",          # write-only — never returned
            "base_url", "temperature", "max_tokens",
            "system_prompt_prefix", "is_active", "is_default",
            "tool_assignments",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_temperature(self, value):
        if not (0.0 <= value <= 2.0):
            raise serializers.ValidationError("Temperature must be between 0.0 and 2.0.")
        return value

    def validate(self, attrs):
        provider = attrs.get("provider", getattr(self.instance, "provider", None))
        base_url = attrs.get("base_url", getattr(self.instance, "base_url", ""))
        if provider == LLMModel.PROVIDER_OLLAMA and not base_url:
            raise serializers.ValidationError(
                {"base_url": "base_url is required for Ollama provider."}
            )
        return attrs


class LLMModelListSerializer(serializers.ModelSerializer):
    """Compact serializer for list view — no tool assignments or write-only key."""
    class Meta:
        model = LLMModel
        fields = [
            "id", "name", "provider", "model_id",
            "is_active", "is_default", "created_at",
        ]
        read_only_fields = fields


class ToolAssignmentWriteSerializer(serializers.Serializer):
    tool_id = serializers.PrimaryKeyRelatedField(queryset=Tool.objects.filter(is_active=True))
    priority = serializers.IntegerField(min_value=0, default=0)
