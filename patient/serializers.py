from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Patient


class PatientRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    name = serializers.CharField(max_length=255)
    age = serializers.IntegerField(min_value=0)
    gender = serializers.ChoiceField(choices=["male", "female", "other", "prefer_not_to_say"])
    phone = serializers.CharField(max_length=20)

    def validate_email(self, value):
        if Patient.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_phone(self, value):
        if Patient.objects.filter(phone=value).exists():
            raise serializers.ValidationError("An account with this phone number already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        patient = Patient(
            email=validated_data["email"],
            name=validated_data["name"],
            age=validated_data["age"],
            gender=validated_data["gender"],
            phone=validated_data["phone"],
            role="patient",
        )
        patient.set_password(validated_data["password"])
        patient.save()
        return patient


class PatientLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled.")
        try:
            patient = Patient.objects.get(pk=user.pk)
        except Patient.DoesNotExist:
            raise serializers.ValidationError("No patient account found for these credentials.")
        attrs["patient"] = patient
        return attrs


class PatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ["patient_id", "name", "age", "gender", "phone", "email", "date_joined"]
        read_only_fields = fields
