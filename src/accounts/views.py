from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

from .serializers import (
    RegisterSerializer, CustomUserSerializer, UserProfileSerializer,
    UpdateCurrentUserSerializer, ChangePasswordSerializer,
    AdminUserListSerializer, UserRoleUpdateSerializer,
    OfficerVerificationSerializer, AuditLogSerializer
)
from .models import UserProfile, AuditLog
from .utils import log_audit, verify_nid_document

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        citizenship_number = request.data.get('citizenship_number', '').strip()
        nid_document = request.FILES.get('nid_document')
        nid_verified = False

        # An identity document supplied at registration must be verified before
        # creating the account; never create a silently unverified identity.
        if citizenship_number or nid_document:
            nid_verified, verification_message = verify_nid_document(
                citizenship_number, nid_document
            )
            if not nid_verified:
                return Response(
                    {'nid_document': [verification_message]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        user = serializer.save()

        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        log_audit(
            category=AuditLog.Category.AUTH,
            action=f"Registered new user account '{user.username}' with role '{user.get_role_display()}'.",
            user=user,
            ip_address=ip,
            status=AuditLog.Status.SUCCESS
        )

        # --- Server-side NID OCR verification ---
        # nid_verified can only become True here; any frontend flag is ignored.
        citizenship_number = request.data.get('citizenship_number', '').strip()
        nid_document = request.FILES.get('nid_document')

        # Verification is performed before account creation above. Keep this
        # legacy branch unreachable while deployed clients transition.
        if False:
            try:
                ocr_text = perform_ocr_on_image(nid_document)
                candidates = extract_nid_candidates(ocr_text)
                entered_norm = normalize_nid(citizenship_number)
                ocr_matched = bool(ocr_text.strip()) and any(
                    normalize_nid(c) == entered_norm for c in candidates
                )
            except Exception:
                # OCR unavailable or image unreadable → fail-closed
                ocr_matched = False

            if ocr_matched:
                profile = user.profile
                profile.nid_verified = True
                profile.save(update_fields=['nid_verified'])

        if nid_verified:
            profile = user.profile
            profile.nid_verified = True
            profile.save(update_fields=['nid_verified'])
            log_audit(
                category=AuditLog.Category.AUTH,
                action=f"Verified NID/Citizenship document by OCR during registration for '{user.username}'.",
                user=user,
                ip_address=ip,
                status=AuditLog.Status.SUCCESS,
            )

        user_data = CustomUserSerializer(user, context=self.get_serializer_context()).data

        return Response({
            'user': user_data,
            'nid_verified': nid_verified,
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
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def perform_update(self, serializer):
        profile = serializer.instance
        has_nid_change = (
            'citizenship_number' in serializer.validated_data
            or 'nid_document' in serializer.validated_data
        )

        if not has_nid_change:
            serializer.save()
            return

        citizenship_number = serializer.validated_data.get(
            'citizenship_number', profile.citizenship_number
        )
        nid_document = serializer.validated_data.get('nid_document', profile.nid_document)
        verified, message = verify_nid_document(citizenship_number, nid_document)
        if not verified:
            raise ValidationError({'nid_document': [message]})

        serializer.save(nid_verified=True)
        log_audit(
            category=AuditLog.Category.AUTH,
            action=f"Verified NID/Citizenship document by OCR for '{self.request.user.username}'.",
            user=self.request.user,
            ip_address=self.request.META.get('REMOTE_ADDR', '127.0.0.1'),
            status=AuditLog.Status.SUCCESS,
        )


class UpdateCurrentUserView(APIView):
    """Allows user to update their own basic account fields (username, email, phone)."""
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        serializer = UpdateCurrentUserSerializer(instance=request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        log_audit(
            category=AuditLog.Category.AUTH,
            action=f"Updated personal account information for '{user.username}'.",
            user=user,
            ip_address=ip,
            status=AuditLog.Status.SUCCESS
        )

        return Response({
            'message': 'Account details updated successfully.',
            'user': CustomUserSerializer(user).data
        }, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """Allows logged-in user to change their password securely."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        log_audit(
            category=AuditLog.Category.AUTH,
            action=f"Changed account password for user '{user.username}'.",
            user=user,
            ip_address=ip,
            status=AuditLog.Status.SUCCESS
        )

        return Response({'message': 'Password changed successfully. Please log in again.'}, status=status.HTTP_200_OK)


class AdminUserListView(generics.ListAPIView):
    """List all users in the system. Admin/staff only."""
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

        if target_user.pk == user.pk:
            return Response(
                {'detail': 'You cannot change your own role.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = UserRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_role = target_user.get_role_display()
        new_role = serializer.validated_data['role']
        target_user.role = new_role
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
