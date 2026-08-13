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

