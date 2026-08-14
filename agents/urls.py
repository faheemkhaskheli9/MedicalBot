from django.urls import path

from . import views

urlpatterns = [
    path("agents/", views.AgentListCreateView.as_view(), name="agent-list-create"),
    path("agents/<uuid:agent_id>/", views.AgentDetailView.as_view(), name="agent-detail"),
    path("agents/<uuid:agent_id>/sessions/", views.AgentSessionListCreateView.as_view(), name="agent-session-list"),
    path("agents/<uuid:agent_id>/facts/", views.AgentFactListView.as_view(), name="agent-fact-list"),
    path("agents/<uuid:agent_id>/facts/<uuid:fact_id>/", views.AgentFactDeleteView.as_view(), name="agent-fact-delete"),
    path("sessions/<uuid:session_id>/", views.AgentSessionDetailView.as_view(), name="agent-session-detail"),
    path("sessions/<uuid:session_id>/messages/", views.AgentMessageView.as_view(), name="agent-messages"),
]
