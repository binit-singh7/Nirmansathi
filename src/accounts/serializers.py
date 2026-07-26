from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserProfile

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
