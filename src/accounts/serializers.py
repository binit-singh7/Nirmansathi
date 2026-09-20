from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserProfile, AuditLog


User = get_user_model()

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'id', 'full_name', 'citizenship_number',
            'nid_document', 'nid_verified',
            'company_name', 'company_pan_vat',
            'address', 'bio', 'avatar',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'nid_verified', 'created_at', 'updated_at']


class CustomUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    municipality_name = serializers.ReadOnlyField(source='municipality.name')

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number',
            'role', 'municipality', 'municipality_name',
            'verification_status', 'verified_at', 'rejection_reason',
            'profile', 'is_active', 'date_joined'
        ]
        read_only_fields = ['id', 'verification_status', 'verified_at', 'rejection_reason', 'is_active', 'date_joined']


class UpdateCurrentUserSerializer(serializers.ModelSerializer):
    """Allows user to update their own username, email, and phone."""
    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number']

    def validate_email(self, value):
        user = self.instance
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_username(self, value):
        if len(value) < 3:
            raise serializers.ValidationError('Username must be at least 3 characters long.')
        user = self.instance
        if User.objects.exclude(pk=user.pk).filter(username=value).exists():
            raise serializers.ValidationError('A user with this username already exists.')
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'New passwords do not match.'})
        return data

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    full_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    citizenship_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    nid_document = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password', 'role',
            'phone_number', 'municipality', 'full_name',
            'citizenship_number', 'nid_document'
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
        citizenship_number = validated_data.pop('citizenship_number', '')
        nid_document = validated_data.pop('nid_document', None)
        password = validated_data.pop('password')

        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        if user.role == User.Role.MUNICIPALITY_OFFICER:
            user.verification_status = User.VerificationStatus.PENDING
            user.save(update_fields=['verification_status'])
        else:
            user.verification_status = User.VerificationStatus.NOT_APPLICABLE
            user.save(update_fields=['verification_status'])

        # Create profile automatically — store NID document if provided.
        # nid_verified is intentionally left False here; it is only set True
        # by RegisterView after a confirmed server-side OCR match.
        profile = UserProfile.objects.create(
            user=user,
            full_name=full_name,
            citizenship_number=citizenship_number or '',
        )
        if nid_document:
            profile.nid_document = nid_document
            profile.nid_verified = False  # must be confirmed by OCR, not assumed
            profile.save(update_fields=['nid_document', 'nid_verified'])

        return user



class AdminUserListSerializer(serializers.ModelSerializer):
    """Read-only serializer for admin user directory listing."""
    profile = UserProfileSerializer(read_only=True)
    municipality_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role', 'phone_number',
            'municipality', 'municipality_name', 'verification_status',
            'verified_at', 'rejection_reason',
            'profile', 'is_active', 'date_joined'
        ]

    def get_municipality_name(self, obj):
        return obj.municipality.name if obj.municipality else None


class OfficerVerificationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['APPROVE', 'REJECT'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if data['action'] == 'REJECT' and not data.get('rejection_reason', '').strip():
            raise serializers.ValidationError({'rejection_reason': 'Rejection reason is required when rejecting an officer.'})
        return data


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
