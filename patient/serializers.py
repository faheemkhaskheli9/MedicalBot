from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Patient


class PatientRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = Patient
        fields = ["patient_id", "name", "age", "gender", "phone", "email", "password", "password_confirm"]
        read_only_fields = ["patient_id"]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        return Patient.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            name=validated_data["name"],
            age=validated_data["age"],
            gender=validated_data["gender"],
            phone=validated_data["phone"],
        )


class PatientLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["email"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled.")
        attrs["user"] = user
        return attrs


class PatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ["patient_id", "name", "age", "gender", "phone", "email", "date_joined"]
        read_only_fields = ["patient_id", "name", "age", "gender", "phone", "email", "date_joined"]
