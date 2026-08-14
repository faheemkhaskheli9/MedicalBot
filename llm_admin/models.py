import uuid
from django.db import models


class LLMModel(models.Model):
    PROVIDER_OPENAI = "openai"
    PROVIDER_ANTHROPIC = "anthropic"
    PROVIDER_GOOGLE = "google"
    PROVIDER_OLLAMA = "ollama"
    PROVIDER_CHOICES = [
        (PROVIDER_OPENAI, "OpenAI"),
        (PROVIDER_ANTHROPIC, "Anthropic"),
        (PROVIDER_GOOGLE, "Google"),
        (PROVIDER_OLLAMA, "Ollama"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    model_id = models.CharField(max_length=100, help_text="e.g. gpt-4o-mini, claude-sonnet-4-6")
    api_key = models.CharField(max_length=500, blank=True, help_text="Leave blank to use environment variable")
    base_url = models.URLField(blank=True, help_text="Required for Ollama (e.g. http://localhost:11434)")
    temperature = models.FloatField(default=0.7)
    max_tokens = models.IntegerField(null=True, blank=True)
    system_prompt_prefix = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    tools = models.ManyToManyField("Tool", through="LLMModelTool", blank=True, related_name="llm_models")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LLM Model"
        ordering = ["-is_default", "name"]

    def __str__(self):
        return f"{self.name} ({self.provider}/{self.model_id})"

    def save(self, *args, **kwargs):
        if self.is_default:
            LLMModel.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class Tool(models.Model):
    TYPE_BUILTIN = "built_in"
    TYPE_LLM_SUBAGENT = "llm_subagent"
    TYPE_CUSTOM = "custom_python"
    TYPE_CHOICES = [
        (TYPE_BUILTIN, "Built-in"),
        (TYPE_LLM_SUBAGENT, "LLM Subagent"),
        (TYPE_CUSTOM, "Custom Python"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.SlugField(max_length=100, unique=True)
    display_name = models.CharField(max_length=200)
    description = models.TextField(help_text="Shown to the LLM as the tool description")
    tool_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_BUILTIN)
    implementation = models.CharField(
        max_length=300, blank=True,
        help_text="Dotted Python path for built_in/custom tools (e.g. llm_admin.builtin_tools.web_search.run)"
    )
    llm_model = models.ForeignKey(
        LLMModel, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="subagent_tools",
        help_text="Populated only when tool_type=llm_subagent"
    )
    parameters_schema = models.JSONField(
        default=dict,
        help_text="OpenAI function-calling JSON schema for this tool's inputs"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tool"
        ordering = ["name"]

    def __str__(self):
        return f"{self.display_name} ({self.tool_type})"


class LLMModelTool(models.Model):
    llm_model = models.ForeignKey(LLMModel, on_delete=models.CASCADE, related_name="tool_assignments")
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name="model_assignments")
    priority = models.PositiveIntegerField(default=0, help_text="Lower number = higher priority")

    class Meta:
        unique_together = [("llm_model", "tool")]
        ordering = ["priority"]
        verbose_name = "Model-Tool Assignment"

    def __str__(self):
        return f"{self.llm_model.name} → {self.tool.name} (priority={self.priority})"
