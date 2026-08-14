from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Agent, AgentFact, AgentSession
from .serializers import (
    AgentFactSerializer,
    AgentMessageSerializer,
    AgentSerializer,
    AgentSessionDetailSerializer,
    AgentSessionSerializer,
    SendMessageSerializer,
)
from .services import send_message


class AgentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        agents = Agent.objects.filter(user=request.user)
        return Response(AgentSerializer(agents, many=True).data)

    def post(self, request):
        serializer = AgentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AgentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_agent(self, request, agent_id):
        try:
            return Agent.objects.get(id=agent_id, user=request.user)
        except Agent.DoesNotExist:
            return None

    def get(self, request, agent_id):
        agent = self._get_agent(request, agent_id)
        if not agent:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(AgentSerializer(agent).data)

    def put(self, request, agent_id):
        agent = self._get_agent(request, agent_id)
        if not agent:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = AgentSerializer(agent, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, agent_id):
        agent = self._get_agent(request, agent_id)
        if not agent:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = AgentSerializer(agent, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, agent_id):
        agent = self._get_agent(request, agent_id)
        if not agent:
            return Response(status=status.HTTP_404_NOT_FOUND)
        agent.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgentSessionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_agent(self, request, agent_id):
        try:
            return Agent.objects.get(id=agent_id, user=request.user)
        except Agent.DoesNotExist:
            return None

    def get(self, request, agent_id):
        agent = self._get_agent(request, agent_id)
        if not agent:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(AgentSessionSerializer(agent.sessions.all(), many=True).data)

    def post(self, request, agent_id):
        agent = self._get_agent(request, agent_id)
        if not agent:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = AgentSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(agent=agent)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AgentSessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_session(self, request, session_id):
        try:
            return AgentSession.objects.select_related("agent").get(
                id=session_id, agent__user=request.user
            )
        except AgentSession.DoesNotExist:
            return None

    def get(self, request, session_id):
        session = self._get_session(request, session_id)
        if not session:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(AgentSessionDetailSerializer(session).data)

    def patch(self, request, session_id):
        session = self._get_session(request, session_id)
        if not session:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = AgentSessionSerializer(session, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, session_id):
        session = self._get_session(request, session_id)
        if not session:
            return Response(status=status.HTTP_404_NOT_FOUND)
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgentMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_session(self, request, session_id):
        try:
            return AgentSession.objects.select_related("agent").get(
                id=session_id, agent__user=request.user
            )
        except AgentSession.DoesNotExist:
            return None

    def get(self, request, session_id):
        session = self._get_session(request, session_id)
        if not session:
            return Response(status=status.HTTP_404_NOT_FOUND)
        msgs = session.messages.filter(is_summarized=False).order_by("created_at")
        return Response(AgentMessageSerializer(msgs, many=True).data)

    def post(self, request, session_id):
        session = self._get_session(request, session_id)
        if not session:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not session.is_active:
            return Response(
                {"detail": "This session is closed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply = send_message(session, serializer.validated_data["content"])
        return Response({"reply": reply}, status=status.HTTP_201_CREATED)


class AgentFactListView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_agent(self, request, agent_id):
        try:
            return Agent.objects.get(id=agent_id, user=request.user)
        except Agent.DoesNotExist:
            return None

    def get(self, request, agent_id):
        agent = self._get_agent(request, agent_id)
        if not agent:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(AgentFactSerializer(agent.facts.all(), many=True).data)


class AgentFactDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, agent_id, fact_id):
        try:
            fact = AgentFact.objects.get(
                id=fact_id, agent__id=agent_id, agent__user=request.user
            )
        except AgentFact.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        fact.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
