from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.reverse import reverse


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    return Response(
        {
            "patient": {
                "register": reverse("patient-register", request=request),
                "login": reverse("patient-login", request=request),
                "logout": reverse("patient-logout", request=request),
                "profile": reverse("patient-profile", request=request),
                "chat_sessions": reverse("chat-sessions", request=request),
            },
        }
    )


def home(request):
    steps = [
        {
            "number": "1",
            "title": "Send a Message",
            "description": "Describe your symptoms or question in plain language via the chat interface.",
        },
        {
            "number": "2",
            "title": "Emergency Triage",
            "description": "Every message is screened for emergencies before anything else happens.",
        },
        {
            "number": "3",
            "title": "Agent Routing",
            "description": "The orchestrator routes your request to the most relevant specialist agent.",
        },
        {
            "number": "4",
            "title": "Doctor Review",
            "description": "Structured data is surfaced to your doctor — who makes all final decisions.",
        },
    ]
    return render(request, "home.html", {"steps": steps})
