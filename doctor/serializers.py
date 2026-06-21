from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Doctor, SPECIALIZATION_CHOICES


class DoctorRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    name = serializers.CharField(max_length=255)
    specialization = serializers.ChoiceField(
        choices=[c[0] for c in SPECIALIZATION_CHOICES],
        default="general_practice",
    )
    license_number = serializers.CharField(max_length=100)

    def validate_email(self, value):
        from users.models import User
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_license_number(self, value):
        if Doctor.objects.filter(license_number=value).exists():
            raise serializers.ValidationError("A doctor with this license number already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        doctor = Doctor(
            email=validated_data["email"],
            name=validated_data["name"],
            specialization=validated_data["specialization"],
            license_number=validated_data["license_number"],
            role="doctor",
        )
        doctor.set_password(validated_data["password"])
        doctor.save()
        return doctor


class DoctorLoginSerializer(serializers.Serializer):
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
            doctor = Doctor.objects.get(pk=user.pk)
        except Doctor.DoesNotExist:
            raise serializers.ValidationError("No doctor account found for these credentials.")
        attrs["doctor"] = doctor
        return attrs


class DoctorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = ["id", "name", "email", "specialization", "license_number", "date_joined"]
        read_only_fields = fields


class PatientSessionListSerializer(serializers.Serializer):
    """Lightweight view of a patient session for the doctor portal."""
    session_id = serializers.UUIDField(source="id")
    patient_name = serializers.SerializerMethodField()
    patient_age = serializers.SerializerMethodField()
    status = serializers.CharField()
    risk_level = serializers.CharField(allow_null=True)
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    message_count = serializers.SerializerMethodField()
    has_summary = serializers.SerializerMethodField()
    last_intent = serializers.SerializerMethodField()

    def get_patient_name(self, obj):
        return obj.patient.name

    def get_patient_age(self, obj):
        return obj.patient.age

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_has_summary(self, obj):
        return obj.summary is not None

    def get_last_intent(self, obj):
        return obj.session_metadata.get("last_intent")


class PatientSessionDetailSerializer(serializers.Serializer):
    """Full session detail for the doctor portal."""
    session_id = serializers.UUIDField(source="id")
    patient_name = serializers.SerializerMethodField()
    patient_age = serializers.SerializerMethodField()
    patient_gender = serializers.SerializerMethodField()
    patient_phone = serializers.SerializerMethodField()
    status = serializers.CharField()
    risk_level = serializers.CharField(allow_null=True)
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    session_metadata = serializers.DictField()
    summary = serializers.DictField(allow_null=True)
    messages = serializers.SerializerMethodField()

    def get_patient_name(self, obj):
        return obj.patient.name

    def get_patient_age(self, obj):
        return obj.patient.age

    def get_patient_gender(self, obj):
        return obj.patient.gender

    def get_patient_phone(self, obj):
        return obj.patient.phone

    def get_messages(self, obj):
        return [
            {
                "sender": m.sender,
                "content": m.content,
                "agent_name": m.agent_name,
                "created_at": m.created_at.isoformat(),
            }
            for m in obj.messages.order_by("created_at")
        ]
