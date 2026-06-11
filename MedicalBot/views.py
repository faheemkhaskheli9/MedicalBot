from django.shortcuts import render


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
