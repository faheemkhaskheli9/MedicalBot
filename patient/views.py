from django.shortcuts import render
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import PatientLoginSerializer, PatientProfileSerializer, PatientRegisterSerializer


def register_page(request):
    return render(request, "patient/register.html")


def login_page(request):
    return render(request, "patient/login.html")


class PatientRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = serializer.save()
        refresh = RefreshToken.for_user(patient)
        return Response(
            {
                "message": "Registration successful.",
                "patient_id": str(patient.patient_id),
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class PatientLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(patient)
        return Response(
            {
                "patient_id": str(patient.patient_id),
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            }
        )


class PatientProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = PatientProfileSerializer(request.user)
        return Response(serializer.data)
