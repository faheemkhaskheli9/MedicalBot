from django.urls import path
from . import views

app_name = "llm_admin"

urlpatterns = [
    # LLM Model endpoints
    path("models/", views.LLMModelListCreateView.as_view(), name="model-list-create"),
    path("models/<uuid:pk>/", views.LLMModelDetailView.as_view(), name="model-detail"),
    path("models/<uuid:pk>/test/", views.LLMModelTestView.as_view(), name="model-test"),
    path("models/<uuid:pk>/set-default/", views.LLMModelSetDefaultView.as_view(), name="model-set-default"),
    path("models/<uuid:pk>/tools/", views.LLMModelToolListCreateView.as_view(), name="model-tool-list-create"),
    path("models/<uuid:model_pk>/tools/<uuid:tool_pk>/", views.LLMModelToolDeleteView.as_view(), name="model-tool-delete"),

    # Tool endpoints
    path("tools/", views.ToolListCreateView.as_view(), name="tool-list-create"),
    path("tools/<uuid:pk>/", views.ToolDetailView.as_view(), name="tool-detail"),
]
