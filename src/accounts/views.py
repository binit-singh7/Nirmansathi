from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

from .serializers import RegisterSerializer, CustomUserSerializer, UserProfileSerializer
from .models import UserProfile, AuditLog
from .utils import log_audit

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        log_audit(
            category=AuditLog.Category.AUTH,
            action=f"Registered new user account '{user.username}' with role '{user.get_role_display()}'.",
            user=user,
            ip_address=ip,
            status=AuditLog.Status.SUCCESS
        )

        user_data = CustomUserSerializer(user, context=self.get_serializer_context()).data
        
        return Response({
            'user': user_data,
            'message': 'User registered successfully. Please login to continue.'
        }, status=status.HTTP_201_CREATED)


class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class AdminUserListView(generics.ListAPIView):
    """List all users in the system. Admin/staff only."""
    from .serializers import AdminUserListSerializer
    serializer_class = AdminUserListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not (user.is_staff or user.role == 'ADMIN'):
            return User.objects.none()
        return User.objects.select_related('municipality', 'profile').order_by('-date_joined')


class AdminUserRoleUpdateView(APIView):
    """Update a user's role. Admin/staff only."""
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        user = request.user
        if not (user.is_staff or user.role == 'ADMIN'):
            return Response(
                {'detail': 'You do not have permission to perform this action.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            target_user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {'detail': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Prevent admins from demoting themselves
        if target_user.pk == user.pk:
            return Response(
                {'detail': 'You cannot change your own role.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from .serializers import UserRoleUpdateSerializer
        serializer = UserRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_role = target_user.get_role_display()
        new_role = serializer.validated_data['role']
        target_user.role = new_role
        # Sync is_staff flag for ADMIN role
        target_user.is_staff = (new_role == 'ADMIN')
        target_user.save(update_fields=['role', 'is_staff'])

        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        log_audit(
            category=AuditLog.Category.ADMIN,
            action=f"Changed role for user '{target_user.username}' from '{old_role}' to '{target_user.get_role_display()}'.",
            user=user,
            ip_address=ip,
            status=AuditLog.Status.SUCCESS
        )

        return Response({
            'id': target_user.pk,
            'username': target_user.username,
            'role': target_user.role,
            'message': f"Role updated to {target_user.get_role_display()} successfully."
        })


class AuditLogListView(generics.ListAPIView):
    """List system audit logs. Admin/staff only."""
    from .serializers import AuditLogSerializer
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not (user.is_staff or user.role == 'ADMIN'):
            return AuditLog.objects.none()

        queryset = AuditLog.objects.all().order_by('-timestamp')

        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        search = self.request.query_params.get('search') or self.request.query_params.get('q')
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(action__icontains=search) |
                Q(actor_username__icontains=search) |
                Q(ip_address__icontains=search)
            )

        return queryset


class AdminOfficerVerificationView(APIView):
    """
    Admin verification endpoint for municipality officers.
    POST /api/v1/accounts/officers/<id>/verify/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from django.utils import timezone
        from .serializers import OfficerVerificationSerializer, CustomUserSerializer

        user = request.user
        if not (user.is_staff or user.role == 'ADMIN'):
            return Response(
                {'detail': 'You do not have permission to perform this action.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            officer = User.objects.get(pk=pk, role=User.Role.MUNICIPALITY_OFFICER)
        except User.DoesNotExist:
            return Response(
                {'detail': 'Municipality officer not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = OfficerVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data['action']
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')

        if action == 'APPROVE':
            officer.verification_status = User.VerificationStatus.APPROVED
            officer.verified_by = user
            officer.verified_at = timezone.now()
            officer.rejection_reason = None
            officer.save(update_fields=['verification_status', 'verified_by', 'verified_at', 'rejection_reason'])

            log_audit(
                category=AuditLog.Category.ADMIN,
                action=f"Approved municipality officer account '{officer.username}' for jurisdiction '{officer.municipality.name if officer.municipality else 'Unassigned'}'.",
                user=user,
                ip_address=ip,
                status=AuditLog.Status.SUCCESS
            )

            return Response({
                'message': f"Officer '{officer.username}' has been successfully verified and approved.",
                'officer': CustomUserSerializer(officer).data
            }, status=status.HTTP_200_OK)

        elif action == 'REJECT':
            reason = serializer.validated_data.get('rejection_reason', '')
            officer.verification_status = User.VerificationStatus.REJECTED
            officer.verified_by = user
            officer.verified_at = timezone.now()
            officer.rejection_reason = reason
            officer.save(update_fields=['verification_status', 'verified_by', 'verified_at', 'rejection_reason'])

            log_audit(
                category=AuditLog.Category.ADMIN,
                action=f"Rejected municipality officer account '{officer.username}'. Reason: {reason}",
                user=user,
                ip_address=ip,
                status=AuditLog.Status.SUCCESS
            )

            return Response({
                'message': f"Officer '{officer.username}' has been rejected.",
                'officer': CustomUserSerializer(officer).data
            }, status=status.HTTP_200_OK)

