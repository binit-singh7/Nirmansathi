from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserProfile, AuditLog


User = get_user_model()

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'id', 'full_name', 'citizenship_number',
            'company_name', 'company_pan_vat', 'address', 'avatar',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CustomUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    municipality_name = serializers.ReadOnlyField(source='municipality.name')

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number',
            'role', 'municipality', 'municipality_name',
            'profile', 'is_active', 'date_joined'
        ]
        read_only_fields = ['id', 'is_active', 'date_joined']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    full_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password', 'role',
            'phone_number', 'municipality', 'full_name'
        ]

    def validate_username(self, value):
        if len(value) < 3:
            raise serializers.ValidationError('Username must be at least 3 characters long.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_phone_number(self, value):
        if value and (not value.isdigit() or len(value) != 10):
            raise serializers.ValidationError('Phone number must be exactly 10 digits.')
        return value

    def validate_password(self, value):
        if len(value) < 6:
            raise serializers.ValidationError('Password must be at least 6 characters long.')
        return value

    def create(self, validated_data):
        full_name = validated_data.pop('full_name', '')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        
        # Create profile automatically
        UserProfile.objects.create(user=user, full_name=full_name)
        return user


class AdminUserListSerializer(serializers.ModelSerializer):
    """Read-only serializer for admin user directory listing."""
    profile = UserProfileSerializer(read_only=True)
    municipality_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role', 'phone_number',
            'municipality', 'municipality_name',
            'is_active', 'is_staff', 'date_joined', 'profile'
        ]
        read_only_fields = fields

    def get_municipality_name(self, obj):
        return obj.municipality.name if obj.municipality else None


class UserRoleUpdateSerializer(serializers.Serializer):
    """Serializer for updating a user's role."""
    role = serializers.ChoiceField(choices=User.Role.choices)


class AuditLogSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'timestamp', 'category', 'category_display',
            'actor', 'actor_username', 'action', 'ip_address',
            'status', 'status_display', 'metadata'
        ]
        read_only_fields = fields

