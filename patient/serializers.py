from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Appointment, ChatSession, EmergencyEvent, MedicalHistory, Message, Patient


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


class MedicalHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalHistory
        fields = [
            "blood_type", "chronic_conditions", "allergies",
            "current_medications", "emergency_contact_name",
            "emergency_contact_phone", "notes", "updated_at",
        ]
        read_only_fields = ["updated_at"]


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "sender", "content", "agent_name", "metadata", "created_at"]
        read_only_fields = ["id", "sender", "agent_name", "metadata", "created_at"]


class EmergencyEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyEvent
        fields = ["id", "trigger_message", "symptoms_detected", "guidance_given", "created_at"]
        read_only_fields = ["id", "trigger_message", "symptoms_detected", "guidance_given", "created_at"]


class AppointmentSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source="doctor.name", read_only=True)
    doctor_specialization = serializers.CharField(source="doctor.specialization", read_only=True)
    session_id = serializers.UUIDField(source="session.id", read_only=True, allow_null=True)

    class Meta:
        model = Appointment
        fields = [
            "id", "doctor", "doctor_name", "doctor_specialization",
            "session_id", "scheduled_at", "reason", "status",
            "doctor_notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "doctor_name", "doctor_specialization", "session_id", "status", "doctor_notes", "created_at", "updated_at"]

    def validate_scheduled_at(self, value):
        from django.utils import timezone
        if value <= timezone.now():
            raise serializers.ValidationError("Appointment must be scheduled in the future.")
        return value


class AssignedDoctorSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    specialization = serializers.CharField(read_only=True)


class ChatSessionSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    emergency_events = EmergencyEventSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    assigned_doctor = AssignedDoctorSerializer(read_only=True)

    class Meta:
        model = ChatSession
        fields = [
            "id", "status", "risk_level", "current_agent", "session_metadata",
            "summary", "started_at", "ended_at", "message_count",
            "assigned_doctor", "messages", "emergency_events",
        ]
        read_only_fields = fields

    def get_message_count(self, obj):
        return obj.messages.count()


class ChatSessionListSerializer(serializers.ModelSerializer):
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    assigned_doctor = AssignedDoctorSerializer(read_only=True)

    class Meta:
        model = ChatSession
        fields = [
            "id", "status", "risk_level", "session_metadata",
            "started_at", "ended_at", "message_count", "last_message", "assigned_doctor",
        ]
        read_only_fields = fields

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_last_message(self, obj):
        msg = obj.messages.filter(sender="patient").last()
        if msg:
            return msg.content[:100]
        return None
