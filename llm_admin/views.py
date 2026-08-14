from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import LLMModel, Tool, LLMModelTool
from .serializers import (
    LLMModelSerializer,
    LLMModelListSerializer,
    ToolSerializer,
    LLMModelToolSerializer,
    ToolAssignmentWriteSerializer,
)
from .permissions import IsHospitalAdmin
from .providers import get_client


class LLMModelListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsHospitalAdmin]

    def get(self, request):
        models = LLMModel.objects.all()
        serializer = LLMModelListSerializer(models, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = LLMModelSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LLMModelDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHospitalAdmin]

    def _get_model(self, pk):
        try:
            return LLMModel.objects.get(pk=pk)
        except LLMModel.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get_model(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(LLMModelSerializer(obj).data)

    def put(self, request, pk):
        obj = self._get_model(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = LLMModelSerializer(obj, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        obj = self._get_model(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = LLMModelSerializer(obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        obj = self._get_model(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LLMModelTestView(APIView):
    """POST /models/{id}/test/ — verify API key and connectivity."""
    permission_classes = [IsAuthenticated, IsHospitalAdmin]

    def post(self, request, pk):
        try:
            obj = LLMModel.objects.get(pk=pk)
        except LLMModel.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            client = get_client(obj)
            ok = client.test_connection()
        except Exception as exc:
            return Response({"ok": False, "error": str(exc)}, status=status.HTTP_200_OK)
        return Response({"ok": ok})


class LLMModelSetDefaultView(APIView):
    """POST /models/{id}/set-default/ — mark as global default."""
    permission_classes = [IsAuthenticated, IsHospitalAdmin]

    def post(self, request, pk):
        try:
            obj = LLMModel.objects.get(pk=pk)
        except LLMModel.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        obj.is_default = True
        obj.save()
        return Response({"detail": f"'{obj.name}' is now the default model."})


class LLMModelToolListCreateView(APIView):
    """GET/POST /models/{id}/tools/ — list assigned tools / assign a tool."""
    permission_classes = [IsAuthenticated, IsHospitalAdmin]

    def _get_model(self, pk):
        try:
            return LLMModel.objects.get(pk=pk)
        except LLMModel.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get_model(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        assignments = obj.tool_assignments.select_related("tool").order_by("priority")
        return Response(LLMModelToolSerializer(assignments, many=True).data)

    def post(self, request, pk):
        obj = self._get_model(pk)
        if not obj:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ToolAssignmentWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        tool = serializer.validated_data["tool_id"]
        priority = serializer.validated_data.get("priority", 0)
        assignment, created = LLMModelTool.objects.get_or_create(
            llm_model=obj, tool=tool,
            defaults={"priority": priority},
        )
        if not created:
            return Response(
                {"detail": "This tool is already assigned to the model."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(LLMModelToolSerializer(assignment).data, status=status.HTTP_201_CREATED)


class LLMModelToolDeleteView(APIView):
    """DELETE /models/{model_pk}/tools/{tool_pk}/ — remove a tool assignment."""
    permission_classes = [IsAuthenticated, IsHospitalAdmin]

    def delete(self, request, model_pk, tool_pk):
        deleted, _ = LLMModelTool.objects.filter(
            llm_model_id=model_pk, tool_id=tool_pk
        ).delete()
        if not deleted:
            return Response({"detail": "Assignment not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Tool views
# ---------------------------------------------------------------------------

class ToolListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsHospitalAdmin]

    def get(self, request):
        tools = Tool.objects.all()
        return Response(ToolSerializer(tools, many=True).data)

    def post(self, request):
        serializer = ToolSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ToolDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHospitalAdmin]

    def _get_tool(self, pk):
        try:
            return Tool.objects.get(pk=pk)
        except Tool.DoesNotExist:
            return None

    def get(self, request, pk):
        tool = self._get_tool(pk)
        if not tool:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ToolSerializer(tool).data)

    def put(self, request, pk):
        tool = self._get_tool(pk)
        if not tool:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ToolSerializer(tool, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        tool = self._get_tool(pk)
        if not tool:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ToolSerializer(tool, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        tool = self._get_tool(pk)
        if not tool:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        tool.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
