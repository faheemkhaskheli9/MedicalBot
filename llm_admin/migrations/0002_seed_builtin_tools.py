from django.db import migrations


BUILTIN_TOOLS = [
    {
        "name": "web_search",
        "display_name": "Web Search",
        "description": (
            "Search the internet for medical information or general knowledge. "
            "Returns a short summary from DuckDuckGo."
        ),
        "tool_type": "built_in",
        "implementation": "llm_admin.builtin_tools.web_search.run",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "calculator",
        "display_name": "Calculator",
        "description": (
            "Safely evaluate a numeric math expression. "
            "Useful for dosage calculations or unit conversions."
        ),
        "tool_type": "built_in",
        "implementation": "llm_admin.builtin_tools.calculator.run",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A math expression to evaluate, e.g. '(75 * 2) / 1000'",
                },
            },
            "required": ["expression"],
        },
    },
    {
        "name": "patient_records",
        "display_name": "Retrieve Patient Records",
        "description": (
            "Retrieve a patient's medical history including blood type, "
            "chronic conditions, allergies, and current medications."
        ),
        "tool_type": "built_in",
        "implementation": "llm_admin.builtin_tools.patient_records.run",
        "parameters_schema": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "UUID of the patient whose records to fetch",
                },
            },
            "required": ["patient_id"],
        },
    },
]


def seed_tools(apps, schema_editor):
    Tool = apps.get_model("llm_admin", "Tool")
    for data in BUILTIN_TOOLS:
        Tool.objects.get_or_create(name=data["name"], defaults=data)


def unseed_tools(apps, schema_editor):
    Tool = apps.get_model("llm_admin", "Tool")
    names = [t["name"] for t in BUILTIN_TOOLS]
    Tool.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("llm_admin", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_tools, reverse_code=unseed_tools),
    ]
