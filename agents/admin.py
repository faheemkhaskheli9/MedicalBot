from django.contrib import admin
from .models import Agent, AgentSession, AgentMessage, ConversationSummary, AgentFact

admin.site.register(Agent)
admin.site.register(AgentSession)
admin.site.register(AgentMessage)
admin.site.register(ConversationSummary)
admin.site.register(AgentFact)
