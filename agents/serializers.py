from rest_framework import serializers

from .models import Agent, AgentFact, AgentMessage, AgentSession, ConversationSummary


class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ["id", "name", "instructions", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class AgentFactSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentFact
        fields = ["id", "fact", "source_session", "created_at"]
        read_only_fields = ["id", "source_session", "created_at"]


class AgentMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentMessage
        fields = ["id", "role", "content", "created_at"]
        read_only_fields = ["id", "role", "created_at"]


class AgentSessionSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="agent.name", read_only=True)
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = AgentSession
        fields = ["id", "agent", "agent_name", "title", "is_active", "created_at", "message_count"]
        read_only_fields = ["id", "agent", "agent_name", "created_at", "message_count"]

    def get_message_count(self, obj):
        return obj.messages.count()


class AgentSessionDetailSerializer(AgentSessionSerializer):
    recent_messages = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    facts = serializers.SerializerMethodField()

    class Meta(AgentSessionSerializer.Meta):
        fields = AgentSessionSerializer.Meta.fields + ["recent_messages", "summary", "facts"]

    def get_recent_messages(self, obj):
        msgs = obj.messages.filter(is_summarized=False).order_by("created_at")
        return AgentMessageSerializer(msgs, many=True).data

    def get_summary(self, obj):
        latest = obj.summaries.order_by("-created_at").first()
        return latest.content if latest else None

    def get_facts(self, obj):
        return AgentFactSerializer(obj.agent.facts.all(), many=True).data


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(min_length=1)
